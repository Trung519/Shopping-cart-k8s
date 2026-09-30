# Progress: Shopping Cart Frontend

## What's Built

### Core Application
- [x] Vite + React 18 + TypeScript project scaffolding
- [x] TanStack Query + Zustand + React Router provider setup in `main.tsx`
- [x] Keycloak OIDC authentication (`react-oidc-context`)
- [x] Axios instance with Bearer token interceptor
- [x] Protected route component
- [x] Layout with Header (cart badge) + Footer

### Pages
- [x] Home page
- [x] Products listing page (with pagination/filter)
- [x] Product detail page
- [x] Cart page (add, update, remove items, checkout)
- [x] Orders listing page
- [x] Order detail page
- [x] Login callback page (`/callback`)
- [x] 404 Not Found page

### UI Components (`src/components/ui/`)
- [x] Button (with cva variants: default, outline; sizes: sm, default, lg)
- [x] Card
- [x] Input
- [x] Badge
- [x] LoadingSpinner

### Services & Hooks
- [x] `cartStore.ts` — Zustand store with localStorage persistence for itemCount
- [x] `useProducts` hook — TanStack Query for product data
- [x] `src/types/index.ts` — complete type definitions for Product, Cart, Order, User, etc.
- [x] `cn()` utility (clsx + tailwind-merge)
- [x] `format.ts` utilities (currency formatting, date formatting)

### Tests
- [x] `Button.test.tsx` — unit tests for Button component
- [x] `cartStore.test.ts` — unit tests for Zustand store
- [x] `format.test.ts` — unit tests for formatting utilities
- [x] `src/test/setup.ts` — Vitest global setup with jest-dom
- [x] `src/test/test-utils.tsx` — `renderWithProviders` helper
- [x] `e2e/home.spec.ts` (5 tests)
- [x] `e2e/products.spec.ts` (10 tests)
- [x] `e2e/cart.spec.ts` (8 tests)
- [x] `e2e/orders.spec.ts` (9 tests)
- [x] `e2e/navigation.spec.ts` (10 tests)

### Infrastructure
- [x] Dockerfile (multi-stage: Node build + nginx:alpine serve)
- [x] `nginx.conf` with SPA fallback + `/api/*` proxy rules
- [x] `k8s/base/deployment.yaml` (2 replicas, health probes, security context)
- [x] `k8s/base/service.yaml`
- [x] `k8s/base/kustomization.yaml`
- [x] `Makefile` with install, dev, build, test, docker-build, docker-run targets
- [x] `.github/workflows/ci.yml`
- [x] CI workflow pin updated to `build-push-deploy.yml@999f8d7` for multi-arch images (2026-03-17)
- [x] `.env.example`
- [x] `.prettierrc`
- [x] `.eslintrc.cjs`

### Documentation (branch: docs/add-frontend-docs — ready for PR)
- [x] `docs/architecture/README.md` — SPA architecture, Keycloak flow, deployment
- [x] `docs/api/README.md` — REST endpoints + env var references
- [x] `docs/troubleshooting/README.md` — Keycloak, proxy, env var, Playwright issues
- [x] `docs/README.md` — index linking all three docs
- [x] `docs/testing/README.md` — Vitest + Playwright instructions — commit `d659e8b`
- [x] `docs/issues/` — `.gitkeep` + standardization issue log — commit `d659e8b`
- [x] `README.md` reformatted to standard template — commit `38a4ca7` (license MIT→Apache 2.0 fixed)

## What's Pending / Not Yet Confirmed

- [ ] `src/pages/` — individual page files not individually inspected but expected to be complete
- [ ] `src/services/` — service files (api.ts, productService, cartService, orderService) not individually inspected
- [ ] `src/hooks/useCart.ts` and `useOrders.ts` — referenced in docs but not individually verified
- [ ] `src/config/api.ts` — exists but content not read
- [ ] Features directory (`src/features/`) — referenced in README but may be empty

## Known Issues / Limitations

1. **Vite build-time environment variables**: The `VITE_*` env vars are baked into the build at compile time. Changing backend URLs requires a rebuild — this is a known trade-off with Vite.

2. **nginx proxy target**: The `nginx.conf` proxy pass targets are hardcoded to cluster service DNS names. When running Docker locally (not in K8s), the proxy will fail unless services are on a shared Docker network.

3. **Auth in E2E tests**: The Playwright E2E tests in `e2e/` test the SPA directly and likely require Keycloak to be running. If Keycloak is unavailable, auth-dependent tests will fail.

4. **No token refresh handling**: The OIDC configuration uses `oidc-client-ts` defaults. Silent token renewal should work automatically, but edge cases around token expiry during a session are not explicitly handled in application code.

## Test Coverage Scope

| Suite | Count | Scope |
|---|---|---|
| Unit (Vitest) | ~20 tests | Button, cartStore, format utils |
| E2E (Playwright) | 42 tests | Full page flows via browser |

Full component coverage for all pages is not yet confirmed — the unit test suite covers utilities and isolated UI components, with E2E tests handling behavioral coverage of pages.
