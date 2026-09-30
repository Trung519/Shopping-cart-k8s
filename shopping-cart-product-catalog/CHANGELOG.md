# Changelog

## [Unreleased]

### Fixed
- Align k8s manifests with data-layer: correct DATABASE_USER, DATABASE_PASSWORD, RABBITMQ_USER, RABBITMQ_PASSWORD, fix DATABASE_HOST to postgresql-products.shopping-cart-data.svc.cluster.local, fix readiness probe path /health/ready→/health

### Changed
- Reduce deployment replicas from 2 to 1 for dev/test environment; delete HPA (`minReplicas: 2` was scaling pods back up on single-node cluster); will reintroduce in v1.1.0 EKS

## [0.1.0] - 2026-03-14

### Added
- FastAPI product catalog service with SQLAlchemy ORM
- Product CRUD endpoints (list, get, create, update, delete)
- OAuth2/OIDC JWT validation via Keycloak JWKS
- Security middleware: rate limiting, security headers
- RabbitMQ event publisher (InventoryUpdatedEvent)
- Prometheus metrics, health/readiness/liveness probes
- Dockerfile (multi-stage, python:3.11-slim with security upgrades)
- Kubernetes manifests (Deployment, Service, ConfigMap)
- GitHub Actions CI: ruff + mypy lint gate + build/test + Trivy + ghcr.io push
- Branch protection (1 required review + CI status check)
