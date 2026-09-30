# Shopping Integration

Helm-managed runtime dependencies and Istio Gateway API configuration for the
shopping-cart services. Plaintext secrets are never stored in this repository.

## Runbooks

- [Marketplace MVP deployment and rollback](docs/marketplace-mvp-runbook.md)
- [Helm migration and data restore](docs/helm-migration-runbook.md)
- [Argo CD installation and access](docs/argocd-runbook.md)

For the current local cluster, deploy in this order:

```bash
./scripts/install-platform.sh
./scripts/bootstrap-vault.sh
./scripts/deploy-integration.sh
./scripts/configure-keycloak-marketplace.sh
./scripts/deploy-apps.sh
./scripts/verify-oidc-session.sh
```
