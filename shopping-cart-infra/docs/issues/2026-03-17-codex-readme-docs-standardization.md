# Task: Standardize README and docs/ Structure Across All Shopping-Cart App Repos

**Date:** 2026-03-17
**Assigned:** Codex
**Repos:** shopping-cart-basket, shopping-cart-order, shopping-cart-payment, shopping-cart-product-catalog, shopping-cart-frontend
**Branch:** `docs/readme-standardization` (create in each repo)

---

## Goal

Every app repo must have the same `docs/` directory structure and a README formatted to match
the k3d-manager pattern. This ensures consistency across the platform.

---

## Standard docs/ Structure (apply to all 5 repos)

```
docs/
  architecture/README.md    — service design, data flow, key decisions
  api/README.md             — endpoints, request/response, auth
  troubleshooting/README.md — common issues and fixes
  testing/README.md         — unit tests, e2e, how to run
  issues/                   — dated issue log files (keep existing, create dir if missing)
```

---

## Standard README Format

Match the k3d-manager README structure exactly:

```
# <Service Name>

<One paragraph description — what the service does, language/framework, key integrations>

---

## Quick Start

<Minimal commands to get running locally>

---

## Usage

<How to run, key commands, environment variables>

---

## Architecture

<Link to docs/architecture/README.md + one-sentence summary>

---

## Directory Layout

<Tree of src/ structure>

---

## Documentation

### Architecture
- **[Service Architecture](docs/architecture/README.md)** — <one-line description>

### API Reference
- **[API Reference](docs/api/README.md)** — <one-line description>

### Testing
- **[Testing Guide](docs/testing/README.md)** — <one-line description>

### Troubleshooting
- **[Troubleshooting Guide](docs/troubleshooting/README.md)** — <one-line description>

### Issue Logs
- **[<issue title>](<path>)** — <one-line description>  (list most recent 3-5 only)

---

## Releases

| Version | Date | Highlights |
|---|---|---|
| [v0.1.0](<github release URL>) | 2026-03-14 | Initial release |

---

## Related

- [Platform Architecture](https://github.com/wilddog64/shopping-cart-infra/blob/main/docs/architecture.md)
- [shopping-cart-infra](https://github.com/wilddog64/shopping-cart-infra)
```

---

## Per-Repo Instructions

### shopping-cart-basket

**Missing:** `docs/testing/README.md`, `docs/issues/`

1. Create `docs/testing/README.md` — cover:
   - Unit tests: how to run (`go test ./...`), test file locations
   - No E2E tests (basket is backend only)
   - Coverage: `go test -cover ./...`

2. Create `docs/issues/` directory (empty, add `.gitkeep`)

3. Reformat `README.md` to standard format above.
   - Description: Go microservice managing shopping cart sessions with Redis
   - Quick Start: `go run ./cmd/server` or `make run`
   - Keep existing content but reorganize into the standard sections

---

### shopping-cart-order

**Missing:** `docs/testing/README.md`

1. Create `docs/testing/README.md` — cover:
   - Unit tests: Maven (`mvn test`), test locations (`src/test/java`)
   - Integration tests if any
   - Coverage: `mvn test jacoco:report`
   - OWASP dependency check: `mvn verify`

2. Reformat `README.md` to standard format.
   - Description: Java/Spring Boot service handling order creation and management
   - Existing `docs/issues/` has 2 entries — list both in Issue Logs section

---

### shopping-cart-payment

**Missing:** `docs/architecture/README.md`, `docs/troubleshooting/README.md`

1. Create `docs/architecture/README.md` — cover:
   - Go service for payment processing
   - PCI-scope namespace isolation (`shopping-cart-payment` ns)
   - Payment gateway integration pattern (credentials via Vault/ESO)
   - Encryption key management (ExternalSecret)
   - Does NOT share namespace with other services

2. Create `docs/troubleshooting/README.md` — cover:
   - Payment gateway credential errors (ESO sync issues)
   - Namespace isolation — why `shopping-cart-payment` not `shopping-cart-apps`
   - Common Maven wrapper issues (reference existing issue `2026-03-17-ci-maven-wrapper-fix.md`)

3. Reformat `README.md` to standard format.
   - Description: Go service for PCI-scope payment processing
   - Issue Logs: list both existing issues

---

### shopping-cart-product-catalog

**Missing:** `docs/testing/README.md`, `docs/issues/`

1. Create `docs/testing/README.md` — cover:
   - Unit tests: pytest (`pytest tests/`)
   - Coverage: `pytest --cov`
   - Vuln scan: `pip-audit`
   - No E2E tests (backend only)

2. Create `docs/issues/` directory (empty, add `.gitkeep`)

3. Reformat `README.md` to standard format.
   - Description: Python/Flask service managing product inventory and catalog

---

### shopping-cart-frontend

**Missing:** All of `docs/` — create from scratch using content already in README.md

1. Create `docs/architecture/README.md` — extract and expand from README sections:
   - Tech stack table (already in README)
   - Project structure (`src/` layout — already in README)
   - Auth flow: Keycloak OIDC, oidc-client-ts, ProtectedRoute pattern
   - State management: TanStack Query (server state) vs Zustand (client state)
   - API layer: Axios base client, service modules, env var configuration

2. Create `docs/api/README.md` — extract from README:
   - Three backend services: Order (`/api/orders`), Product Catalog (`/api/products`), Basket (`/api/cart`)
   - Auth header pattern (Bearer token via Axios interceptor)
   - Keycloak client configuration (realm, redirect URIs)
   - Environment variables reference (`VITE_*`)

3. Create `docs/troubleshooting/README.md` — write fresh:
   - Keycloak redirect URI mismatch
   - Backend service CORS issues
   - `VITE_*` env vars not set
   - Playwright browser not installed

4. Create `docs/testing/README.md` — extract from README:
   - Unit tests: Vitest + React Testing Library (`npm test`, `npm run test:coverage`)
   - E2E: Playwright (`npm run test:e2e`, `npm run test:e2e:ui`)
   - E2E test coverage table (already in README): home, products, cart, orders, navigation specs
   - `npm run playwright:install` prerequisite

5. Create `docs/issues/` with `.gitkeep`

6. Reformat `README.md` to standard format.
   - Description: React/TypeScript frontend with Keycloak SSO, product browsing, cart, orders
   - Strip out the inline testing/auth/architecture detail — those move to docs/
   - Keep Quick Start, Available Scripts, Docker, Kubernetes sections (operational)

---

## Rules

- Do NOT change any application source code — docs and README only
- Preserve all existing content in `docs/` files — only add, never delete
- Each `docs/*/README.md` file must start with `# <Service> — <Section Title>`
- LF line endings only
- One commit per repo: `docs: standardize README and docs/ structure`
- SHA in completion report for each repo

---

## Completion Criteria

For each repo:
- [ ] All 4 `docs/` subdirectories exist with `README.md`
- [ ] `docs/issues/` directory exists
- [ ] `README.md` follows standard format
- [ ] `git log` shows the commit
- [ ] No source code files modified

Report: one SHA per repo.
