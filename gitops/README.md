# Shopping cart GitOps

Local-review change: do not bootstrap until these files have been reviewed and pushed to `dev`.

## Layout

```text
gitops/bootstrap/root-app.yaml       # Register this one Application once
gitops/control-plane/project.yaml    # Repository and destination permissions
gitops/control-plane/services.yaml   # ApplicationSet: 11 service/chart entries
gitops/validate.py                   # Offline Helm render and ownership checks
```

The root Application reads only `gitops/control-plane`, so it cannot recursively include itself. It creates the AppProject and ApplicationSet. The ApplicationSet creates Applications for eight application services, integration, security and observability. Each child uses the existing Helm release name, destination namespace and chart. Both chart and values sources point at this monorepo on `dev`. Values are applied in order: chart defaults, `00-global.yaml`, then service values. Frontend's deployment tag is controlled by `config-secret-secure/values/local/20-frontend.yaml`.

All Applications use **manual sync**. Creating or updating an Application does not deploy its workload. There is no automated prune or cascade-delete finalizer. The ApplicationSet uses `create-update` and `preserveResourcesOnDeletion: true`: removing a catalog entry does not clean up its existing Application; decommissioning requires an explicit separate decision. Applications remain owned by the ApplicationSet through Kubernetes owner references, so deleting the ApplicationSet itself may delete those Application objects, but preserved workloads are not cascade-deleted by an Argo finalizer.

## Review locally first

Run from the repository root (Python 3, Ruby standard YAML library and Helm are required):

```bash
python3 gitops/validate.py
git diff --stat
git status --short
```

Validation renders charts without contacting Kubernetes. It checks values paths, namespace permissions, cluster resource kinds and resource overlap. It does not prove that Git credentials, local images, Vault, runtime health or rendered desired state match the currently deployed releases.

## Bootstrap after review and push

Ensure the repository is connected in Argo CD. The existing Argo CD installation includes the ApplicationSet controller. After the files are available on remote `dev`, register the root:

```bash
kubectl --context k3d-lab-k8s apply -f gitops/bootstrap/root-app.yaml
```

In Argo CD, open `shopping-cart-root`, inspect Diff and manually Sync it with Prune/Force disabled. It installs the project first and then the ApplicationSet. Wait for 11 child Applications to appear. Root Sync does not sync child workloads.

The already-created `frontend` Application intentionally retains its name; do not delete it to re-import. Before bootstrap, inspect its YAML and confirm it is not owned by another ApplicationSet. The new controller can reconcile this existing standalone Application to the template, including moving it to project `shopping-cart`. Keep any required source overrides in Git because changes made directly to child Application source settings may be overwritten by the ApplicationSet.

## Deploy each workload

Start with `frontend`: check rendered Diff and its image tag, then Sync manually and verify application behavior. Proceed through the remaining application services individually. Review `shopping-integration` separately: its chart includes databases, PVC templates, namespace metadata, Vault's ClusterSecretStore and gateway/identity resources. Check stateful resource differences and existing data before Sync. Review security and observability independently as well.

The charts do not execute the procedural setup/build scripts. Vault bootstrap, image build/import, database restore or migration and prerequisites such as Istio, Gateway API CRDs and External Secrets remain separate operations. Existing placeholder credentials in this source snapshot must not replace live credentials. Once a workload is managed through Argo CD, stop running Helm upgrade scripts against that same workload; do not Helm-uninstall the existing release during migration.

## Add another service

Add an entry under `spec.generators[0].list.elements` in `services.yaml`:

```yaml
- name: new-service
  chartPath: new-service/helmchart
  namespace: shopping-cart-apps
  valuesPath: config-secret-secure/values/local/28-new-service.yaml
```

Provide the chart and values file, run validation, review and push. Refresh and Sync the root Application so the updated ApplicationSet is applied. The controller then creates the new child; manually review and Sync that child when ready. For new destination namespaces, update project permissions too.

## Deploy a new version

Build a uniquely tagged image and push it to a reachable registry, or import it into k3d. Update the service values file, commit/push `dev`, then Refresh, Diff and Sync the child Application. The root need not be synced for an image-only values change. Revert the Git change to return to a previous version.

## Existing legacy definitions

`shopping-cart-infra/argocd/` is the old multi-repository setup (`cicd`, `ubuntu-k3s`, original repository URLs). It is not read by this root Application. Use this `gitops/` entry point for the monorepo; do not bootstrap both definitions.

## References

- [ApplicationSet list generator](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-List/)
- [ApplicationSet specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/applicationset-specification/)
- [Helm and values precedence](https://argo-cd.readthedocs.io/en/latest/user-guide/helm/)
