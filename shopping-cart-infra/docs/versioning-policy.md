# Container Image Versioning Policy

This project uses semantic version tags for all deployable service images:

- `vMAJOR.MINOR.PATCH`
- Example baseline: `v1.0.0`

## Increment Rules

1. Patch (`v1.0.X`)
- Use for bug fixes, hotfixes, and small operational corrections.
- No new feature contract expected.

2. Minor (`v1.X.0`)
- Use for new features or additive changes.
- Backward compatible API and deployment behavior should be preserved.

3. Major (`vX.0.0`)
- Use for breaking changes or significant upgrades.
- Typical triggers: major architecture changes, performance redesign, or compatibility-breaking behavior.

## Operational Rules

- Do not deploy `:latest` for application services.
- Keep manifests and build scripts aligned to the same semantic tag.
- When bumping versions, update:
  - `k8s/base/kustomization.yaml` image `newTag`
  - any hardcoded image references in deployment manifests
  - build/deploy scripts that tag images

## Current Active Baseline

- `shopping-cart-frontend:v1.0.0`
- `shopping-cart-basket:v1.0.0`
- `shopping-cart-order:v1.0.0`
- `shopping-cart-product-catalog:v1.0.0`
