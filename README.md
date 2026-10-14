# Shopping Cart on Kubernetes

This repository collects the local shopping cart source projects into a single repository. Each component is a normal folder at the repository root; there is no enclosing `biglab-k8s` folder and no Git submodules.

## Components

- `shopping-cart-frontend`: frontend application.
- `shopping-cart-basket`, `shopping-cart-product-catalog`, `shopping-cart-order`, `shopping-cart-payment`: shopping services.
- `account-service`, `seller-service`, `commerce-bff`: marketplace services.
- `shopping-integration`: local deployment scripts, runbooks and RabbitMQ event contracts.
- `shopping-observability`: observability docs, SRE scripts and chart tests.
- `charts`: every Helm chart in the repository — `charts/apps/<release>` for application services, `charts/platform/<release>` for integration, security and observability. See [charts/README.md](charts/README.md).
- `config-secret-secure`: per-release Helm values.
- `rabbitmq-client-java`: shared Java RabbitMQ client (built locally by `full-system-test.sh`).
- `shopping-performance`: performance testing tools.
- `gitops`: Argo CD root Application and ApplicationSet.

See each component's README for details.

## Argo CD for this monorepo

The [GitOps setup](gitops/README.md) uses one root Application and an ApplicationSet catalog for the charts above. All workload Applications start with manual sync.

## Credentials and generated files

Nested Git history, dependency/build directories, local environment files and binary artifacts are excluded. Detected credential literals in the publishing copy were replaced with placeholders, and a vendored credential test fixture was omitted. Supply local secrets through environment variables or Vault; never commit live credentials. Placeholder replacement may require local configuration before running affected scripts or tests.

## Branch

The initial source snapshot is published on `dev`.
