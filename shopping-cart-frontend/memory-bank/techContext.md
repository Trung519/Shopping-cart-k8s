# Tech Context: Shopping Cart Frontend

## Core Technology Stack

| Category | Technology | Version |
|---|---|---|
| Language | TypeScript | 5.x (strict mode) |
| Framework | React | 18.2 |
| Build Tool | Vite | 5.x |
| Routing | React Router | 6.21 |
| Server State | TanStack Query (React Query) | 5.17 |
| Client State | Zustand | 4.4 |
| HTTP Client | Axios | 1.6 |
| Auth | oidc-client-ts + react-oidc-context | 2.4 / 2.3 |
| Styling | Tailwind CSS | 3.4 |
| Component Variants | class-variance-authority | 0.7 |
| Class Merging | clsx + tailwind-merge | 2.1 / 2.2 |
| Icons | lucide-react | 0.303 |
| Unit Testing | Vitest | 1.1 |
| Component Testing | React Testing Library | 14.1 |
| DOM Matchers | @testing-library/jest-dom | 6.2 |
| E2E Testing | Playwright | 1.40 |
| Linting | ESLint | 8.56 (typescript-eslint, react-hooks, react-refresh) |
| Formatting | Prettier | 3.1 |

## Runtime Dependencies (production)

```json
@tanstack/react-query, axios, class-variance-authority, clsx,
lucide-react, oidc-client-ts, react, react-dom,
react-oidc-context, react-router-dom, tailwind-merge, zustand
```

## Dev Environment Setup

### Prerequisites
- Node.js 20+
- npm 10+
- A running Keycloak instance (for auth)
- Running backend services OR port-forwarded K8s services

### Install and Run
```bash
git clone <repo>
cd shopping-cart-frontend
npm install
cp .env.example .env.local
# Edit .env.local with correct service URLs
npm run dev
# App runs on http://localhost:3000
```

### Environment File (.env.local)
```env
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=shopping-cart
VITE_CLIENT_ID=frontend
VITE_ORDER_SERVICE_URL=/api/orders
VITE_PRODUCT_SERVICE_URL=/api/products
VITE_CART_SERVICE_URL=/api/cart
```

### Keycloak Client Configuration
The Keycloak `frontend` client must be registered in the `shopping-cart` realm:
- Client type: public (no secret)
- Valid redirect URIs: `http://localhost:3000/*`
- Web origins: `http://localhost:3000`

## Build Configuration

### Vite (vite.config.ts)
- React plugin (`@vitejs/plugin-react`)
- Path alias: `@` → `src/`
- Dev server port: 3000

### TypeScript (tsconfig.json)
- Target: ES2020
- Module: ESNext with bundler resolution
- Path alias: `@/*` → `./src/*`
- Strict mode enabled
- `tsconfig.node.json` for Vite config itself

### Tailwind (tailwind.config.js)
- Content scan: `src/**/*.{ts,tsx}`
- PostCSS integration via `postcss.config.js`

### ESLint (.eslintrc.cjs)
- Extends: typescript-eslint recommended
- Plugins: react-hooks, react-refresh
- Max warnings: 0 (enforced in `npm run lint`)

## Docker & Kubernetes

### Dockerfile
Multi-stage build:
1. Node 20 image — `npm ci && npm run build`
2. nginx:alpine — copy `dist/` into nginx html root

### nginx.conf
- Serves static files from `/usr/share/nginx/html`
- SPA fallback: all non-file 404s return `index.html`
- Proxy rules: `/api/orders` → order service, `/api/products` → product service, `/api/cart` → basket service
- Health endpoint: `GET /health` returns 200

### Kubernetes Manifests (k8s/base/)
- `deployment.yaml`: 2 replicas, image `shopping-cart/frontend:latest`, NodePort 80, health probes, security context (runAsUser: 101)
- `service.yaml`: ClusterIP exposing port 80
- `kustomization.yaml`: base kustomization referencing both manifests
- Resource limits: requests 50m CPU / 64Mi memory, limits 200m CPU / 128Mi memory

## CI/CD

GitHub Actions workflow at `.github/workflows/ci.yml`:
- Triggers: push and pull_request on main
- Steps: checkout → Node 20 setup → npm ci → lint → test → build
- No image push from frontend repo (image push is triggered by the infra pipeline)
