# Copilot Instructions — Shopping Cart Frontend

## Service Overview

React 18 + TypeScript SPA. Vite 5, TanStack Query, Zustand, Tailwind CSS.
OAuth2/OIDC via Keycloak (`react-oidc-context`). nginx proxies `/api/*` to backend services.

---

## Architecture Guardrails

### Layer Boundaries — Never Cross These
- **Pages** (`src/pages/`): route components only — no direct API calls, no business logic
- **Hooks** (`src/hooks/`): TanStack Query hooks — data fetching only
- **Services** (`src/services/`): API client functions — HTTP calls via the base `api.ts` Axios instance
- **Stores** (`src/stores/`): Zustand — client-only state (cart count, UI state)
- A page must never call `axios` or `fetch` directly. Always through a hook or service.

### API Access — Always Through nginx Proxy
- All backend calls must use relative paths (`/api/orders`, `/api/products`, `/api/cart`)
- Never hardcode backend service URLs (`http://order-service:8081`) in frontend code
- Never bypass the nginx proxy to call backend services directly
- `VITE_*` env vars are for Keycloak config and feature flags only — not service URLs

### Authentication
- Tokens must be stored in memory only — never in `localStorage` or `sessionStorage`
- `react-oidc-context` manages the token lifecycle — never store tokens in Zustand or component state
- The Axios interceptor in `src/services/api.ts` adds the Bearer token — never add auth headers manually in individual service functions
- `<ProtectedRoute>` must wrap all pages requiring authentication — never check auth manually in page components
- Never log or expose token values — not even in error messages

### State Management
- Server state (products, orders, cart from backend): TanStack Query only
- Client state (UI state, local cart count): Zustand only
- Never duplicate server state in Zustand — TanStack Query is the source of truth for backend data

---

## Security Rules (treat violations as bugs)

### Secrets and Credentials (OWASP A02)
- No API keys in frontend code — ever. Not in `.env`, not in `VITE_*` vars, not in source.
- Keycloak client ID is not a secret — it can appear in config. Keycloak client secret must never appear in frontend code.
- Never log auth tokens, user credentials, or personal data

### XSS (OWASP A03)
- Never use `dangerouslySetInnerHTML` unless the content is sanitized and the use is explicitly justified
- Never insert user-supplied content into the DOM via string concatenation
- Never use `eval()` or `new Function()`

### Access Control (OWASP A01)
- Never rely on frontend-only checks for authorization — the backend enforces access control
- `<ProtectedRoute>` is a UX guard, not a security boundary
- Never hide sensitive data by simply not rendering it — ensure the API doesn't return it

### Sensitive Data in State
- Never store payment card data in React state or Zustand
- Never store full user profile beyond what is needed for display

---

## Code Quality Rules

### Testing
- All new components require Vitest + React Testing Library tests
- Never delete or comment out existing tests
- Never weaken an assertion (e.g. changing `expect(x).toBe(y)` to `expect(x).toBeTruthy()`)
- Run `npm test` before every commit; must pass clean

### Code Style
- TypeScript strict mode — no `any` types without explicit justification and comment
- Functional components with hooks only — no class components
- Named exports for all components except pages (pages use default export)
- Use `cn()` for class merging — never string concatenate Tailwind classes
- Use `cva()` for component variants — never conditionally apply classes inline
- Prettier formatting must be clean: `npm run format`
- ESLint must be clean: `npm run lint`

### Component Patterns
- New UI primitives go in `src/components/ui/` — reusable, no business logic
- New feature components go in `src/components/` under a feature folder
- Never import from `src/pages/` in components — pages are leaf nodes
- Every new public component must have at least one rendering test

### Dependencies
- Never add a new npm dependency without justification in the PR description
- Never add a dependency that requires access to `localStorage` for auth tokens

---

## Completion Report Requirements

Before marking any task complete, the agent must provide:
- `npm test` output (must be clean)
- `npm run lint` output (must be clean)
- Confirmation that no API key, token, or credential appears in any changed file
- Confirmation that no test was deleted or weakened
- Confirmation that all backend calls go through `/api/*` proxy
- List of exact files modified

---

## What NOT To Do

- Do not store tokens in `localStorage` or `sessionStorage` under any circumstances
- Do not hardcode backend service hostnames or ports
- Do not add `dangerouslySetInnerHTML` without explicit sanitization and justification
- Do not add `any` types as a shortcut to fix TypeScript errors
- Do not duplicate TanStack Query cache data in Zustand
- Do not add client-side business logic that should live in the backend
