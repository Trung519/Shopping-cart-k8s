# Shopping Cart on Kubernetes

This repository collects the local shopping cart source projects into a single repository. Each component is a normal folder at the repository root; there is no enclosing `biglab-k8s` folder and no Git submodules.

## Components

- `shopping-cart-frontend`: frontend application.
- `shopping-cart-basket`, `shopping-cart-product-catalog`, `shopping-cart-order`, `shopping-cart-payment`: shopping services.
- `account-service`, `seller-service`, `commerce-bff`: marketplace services.
- `shopping-integration`: integration Helm chart and local deployment scripts.
- `shopping-cart-infra`: infrastructure scripts and existing Argo CD application definitions.
- `shopping-cart-security`, `shopping-observability`: security and observability charts.
- `config-secret-secure`: deployment values and Vault policies.
- `rabbitmq-client-java`: shared Java RabbitMQ client.
- `shopping-performance`: performance testing tools.
- `jenkinsfile`: existing Jenkins pipeline.

See each component's README for details. This is a source snapshot, not a verified migration of the existing deployment pipelines to this monorepo. Existing Git URLs and relative chart paths in Argo CD definitions still refer to the original repositories and need adjustment before use with this repository.

## Credentials and generated files

Nested Git history, dependency/build directories, local environment files and binary artifacts are excluded. Detected credential literals in the publishing copy were replaced with placeholders, and a vendored credential test fixture was omitted. Supply local secrets through environment variables or Vault; never commit live credentials. Placeholder replacement may require local configuration before running affected scripts or tests.

## Branch

The initial source snapshot is published on `dev`.
