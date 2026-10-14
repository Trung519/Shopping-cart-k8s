# Helm charts

Every Helm chart in this monorepo lives here. Service source code stays in its component folder; only deployment packaging is centralized.

## Layout

```text
charts/
├── library/
│   └── shopping-app/             # Library chart: helpers + standard resources shared by charts/apps/*
├── apps/                         # One chart per application service (Argo CD release name = folder name)
│   ├── frontend/                 # source: shopping-cart-frontend
│   ├── basket-service/           # source: shopping-cart-basket
│   ├── product-catalog/          # source: shopping-cart-product-catalog
│   ├── order-service/            # source: shopping-cart-order
│   ├── payment-service/          # source: shopping-cart-payment
│   ├── commerce-bff/             # source: commerce-bff
│   ├── account-service/          # source: account-service
│   └── seller-service/           # source: seller-service
└── platform/                     # Shared, cluster-level releases
    ├── shopping-integration/     # data stores, Keycloak, Vault ClusterSecretStore, gateway
    ├── shopping-cart-security/   # Istio ingress AuthorizationPolicies
    └── shopping-observability/   # Loki, Fluent Bit, kube-prometheus-stack, Tempo/OTel
```

## Conventions

- Folder name = `name` in `Chart.yaml` = Helm/Argo CD release name.
- Every chart has `values.yaml` (environment-neutral defaults) and `values.schema.json`. Per-environment values (image tag, hosts, cluster identity) live in `config-secret-secure/values/<env>/NN-<release>.yaml`, which `gitops/control-plane/services.yaml` references for every release.
- Image tags are set only in `config-secret-secure`. `appVersion` records the application release the chart was last aligned with; bump chart `version` whenever anything under the chart (or the library it uses) changes.

## Application charts and the `shopping-app` library

Application charts depend on `charts/library/shopping-app` (`repository: file://../../library/shopping-app`). The library owns the helpers (`shopping-app.name`, `.namespace`, `.labels`, `.selectorLabels`, `.configChecksum`) and the standard resources, so each app chart only keeps its Deployment:

| Template file in the app chart | Content |
|--------------------------------|---------|
| `templates/rbac/<release>-serviceaccount.yaml` | `{{- include "shopping-app.serviceaccount" . }}` |
| `templates/networking/<release>-service.yaml` | `{{- include "shopping-app.service" . }}` |
| `templates/networking/<release>-destinationrule.yaml` | `{{- include "shopping-app.destinationrule" . }}` |
| `templates/configmap/<release>-config.yaml` | `{{- include "shopping-app.configmap" . }}` |
| `templates/secret/<release>-secret.yaml` | `{{- include "shopping-app.externalsecret" . }}` |
| `templates/deployment/<release>-deployment.yaml` | chart-specific Deployment using the library helpers |

Values contract read by the library: `serviceName`, `namespaceOverride`, `component` (optional `app.kubernetes.io/component`), `commonLabels`, `serviceAccount.{create,name,automountToken}`, `service.*`, `destinationRule.*`, `config`, `externalSecret.*`.

`checksum/config` hashes only `.Values.config`, so chart version or label changes do not restart pods.

The packaged dependency (`charts/apps/*/charts/shopping-app-*.tgz`) is git-ignored; `Chart.lock` is committed. Build it before using Helm directly:

```bash
for c in charts/apps/*/; do helm dependency build "$c"; done
```

Argo CD runs `helm dependency build` itself; `gitops/validate.py`, `deploy-apps.sh`, `full-system-test.sh` and the service Makefiles also build it. After editing the library, bump its `version` and update the `dependencies[].version` of every app chart.

## Local commands

Run from the repository root:

```bash
helm dependency build charts/apps/basket-service
helm lint charts/apps/basket-service -f config-secret-secure/values/local/21-basket-service.yaml
helm template basket-service charts/apps/basket-service -n shopping-cart-apps -f config-secret-secure/values/local/21-basket-service.yaml
python3 gitops/validate.py
```

`shopping-integration/scripts/deploy-integration.sh` and `deploy-apps.sh` install these charts directly with Helm; once a release is managed by Argo CD, stop using those scripts for it.

## Third-party subcharts (shopping-observability)

`charts/platform/shopping-observability/charts/` vendors Loki and Fluent Bit as unpacked folders (`file://` dependencies) and kube-prometheus-stack as a pinned `.tgz` (listed with its upstream repository in `Chart.lock`). They are committed so Argo CD renders offline and identically; update them only with `helm dependency update` against the pinned versions and review the rendered diff.
