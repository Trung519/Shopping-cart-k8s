# Architecture — Shopping Cart Frontend

## Stack

| Layer | Technology |
|---|---|
| Language | TypeScript 5.x |
| Framework | React 18 |
| Build | Vite 5.x |
| Routing | React Router 6 |
| Server state | TanStack Query |
| Client state | Zustand |
| HTTP | Axios |
| Auth | oidc-client-ts + react-oidc-context |
| Styling | Tailwind CSS 3.x |
| Unit tests | Vitest + React Testing Library |
| E2E tests | Playwright |

## Source Layout

```
src/
├── components/
│   ├── layout/      # Header, Footer, page shell
│   └── ui/          # Reusable primitives (Button, Card, ...)
├── config/          # Auth config (oidcConfig, getAccessToken), API base URLs
├── features/        # Feature-scoped components (ProductList, CartDrawer, ...)
├── hooks/           # TanStack Query wrappers (useProducts, useCart, ...)
├── pages/           # Route-level components (HomePage, CartPage, ...)
├── services/        # Axios API clients per backend service
├── stores/          # Zustand stores (cartStore)
├── test/            # Test utilities and mocks
├── types/           # Shared TypeScript types
└── utils/           # Utility functions
```

## Authentication Flow

Auth state is managed by `react-oidc-context` (`AuthProvider` in `src/main.tsx`, `useAuth` hook
in components). Tokens are stored by `oidc-client-ts` — note that the default storage is
`localStorage`, which is vulnerable to XSS token exfiltration. Consider in-memory storage for
production hardening.

```
User → Login button
     → Keycloak login page (redirect)
     → Token issued (access + refresh)
     → Managed by react-oidc-context / oidc-client-ts
     → Axios interceptor (src/services/api.ts) injects Bearer token on every request
       via getAccessToken() from src/config/auth.ts
```

Protected routes (`/cart`, `/orders`, `/orders/:id`) redirect to Keycloak if unauthenticated.

Keycloak client config:
- Realm: `shopping-cart`
- Client ID: `frontend`
- Client type: `public`

## State Management

| State type | Tool | Example |
|---|---|---|
| Server/async | TanStack Query | product list, order history |
| Client/UI | Zustand | cart item count (`cartStore`) |
| Auth | react-oidc-context | `useAuth()` hook |
| Form | Local component state | checkout form |

## Container

Nginx serves the production build on port 80. `nginx.conf` proxies `/api/*` paths directly
to Kubernetes service DNS names in the `shopping-cart-apps` namespace (e.g.
`order-service.shopping-cart-apps.svc.cluster.local:8081`). Built as a multi-stage Docker
image — Node 20 builder → Nginx Alpine runtime.

## Kubernetes

The `helmchart/` chart deploys to `shopping-cart-apps`. Argo CD uses external values from
the Ubuntu k3s app cluster. Image tag updated by the CI infra workflow on every push to `main`.
