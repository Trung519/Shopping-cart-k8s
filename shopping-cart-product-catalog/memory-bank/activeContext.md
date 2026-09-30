# Active Context: Product Catalog Service

## Current Status (2026-03-14)

CI green. All PRs merged to main. Branch protection active.

## What's Implemented

- FastAPI app with lifespan handler, SQLAlchemy Product model, pydantic-settings config
- Product CRUD endpoints, health/readiness/liveness probes, Prometheus metrics
- OAuth2/OIDC JWT validation (Keycloak JWKS), security middleware (headers, rate limiting)
- RabbitMQ event publisher (InventoryUpdatedEvent etc.)
- Unit tests: test_auth.py, test_auth_integration.py, test_security.py, test_security_middleware.py
- GitHub Actions CI: ruff + mypy lint gate + build/test + Trivy + ghcr.io push

## CI History

- **fix/ci-stabilization PR #1** — merged 2026-03-14. Fixed: Dockerfile security upgrades.
- **feature/p4-linter PR #2** — merged 2026-03-14. Added ruff + mypy lint gate.
- **Branch protection** — 1 review + CI required, enforce_admins: false

## Active Task

- **Multi-arch workflow pin** — branch `fix/multiarch-workflow-pin` updates `.github/workflows/ci.yml` to reference infra SHA `999f8d7` (multi-arch images).
- **v0.1.0 release** — cut `release/v0.1.0` from main, add CHANGELOG, open PR, tag after merge.

## Agent Instructions

Rules that apply to ALL agents working in this repo:

1. **CI only** — do NOT run `pytest` or `mypy` locally without activating the virtualenv.
2. **Memory-bank discipline** — do NOT update `memory-bank/activeContext.md` until CI shows `completed success`.
3. **SHA verification** — verify commit SHA with `gh api repos/wilddog64/shopping-cart-product-catalog/commits/<sha>` before reporting.
4. **Do NOT merge PRs** — open the PR and stop.
5. **No unsolicited changes** — flat structure is intentional, do not refactor to services/repositories.

## Key Notes

- Flat structure (not layered) — do not refactor without team decision
- No Alembic migrations yet — uses `Base.metadata.create_all()` for dev
- `.[rabbitmq]` optional dep installs pika + hvac + tenacity
