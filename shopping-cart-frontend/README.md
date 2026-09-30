# Shopping Cart Frontend

A modern React + TypeScript single-page application powering product discovery, cart management, and order tracking for the Shopping Cart platform. It uses a local login flow backed by basket-service auth endpoints, talks to Order/Product Catalog/Basket services via Axios, and ships as an nginx-served static site.

---

## Quick Start

### Prerequisites
- Node.js 20+
- npm 10+
- Backend services running (Order, Product Catalog, Basket)

### Install & Run
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run unit tests
npm test
```

### Environment Variables
Create `.env.local`:
```env
VITE_AUTH_SERVICE_URL=/api/auth
VITE_ORDER_SERVICE_URL=/api/orders
VITE_PRODUCT_SERVICE_URL=/api/products
VITE_CART_SERVICE_URL=/api/cart
```

---

## Usage

### Features
- **Product Catalog**: Browse and search products
- **Shopping Cart**: Add, update, remove items with real-time totals
- **Order Management**: View order history and details
- **Authentication**: Local username/password login via basket-service auth API
- **Responsive Design**: Mobile-first UI
- **Type Safety**: Full TypeScript coverage

### Technology Stack
| Category | Technology |
|----------|------------|
| Language | TypeScript 5.x |
| Framework | React 18 |
| Build Tool | Vite 5.x |
| Routing | React Router 6 |
| Server State | TanStack Query (React Query) |
| Client State | Zustand |
| API Client | Axios |
| Auth | Local auth context + JWT bearer token |
| Styling | Tailwind CSS 3.x |
| Testing | Vitest + React Testing Library |
| E2E Testing | Playwright |

### Available Scripts
| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server on port 3000 |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run test` | Run unit tests |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run lint` | Run ESLint |
| `npm run format` | Format code with Prettier |

### API Endpoints
| Service | Endpoint Prefix | Description |
|---------|-----------------|-------------|
| Order Service | `/api/orders` | Order management |
| Product Catalog | `/api/products` | Product listing and details |
| Basket Service | `/api/cart` | Shopping cart operations |

### Authentication
Authentication uses local login backed by basket-service:
1. User opens `/login` and signs in with username/password.
2. Frontend stores a short-lived bearer token in local storage.
3. Axios interceptors add `Authorization` and `X-User-ID` headers to API requests.

Protected routes:
- `/cart` — Shopping cart
- `/orders` — Order history
- `/orders/:id` — Order details

Demo credentials:
1. `demo / demo123`
2. `admin / admin123`

### Testing

#### Unit Tests
```bash
npm test
npm run test:coverage
npm test -- src/components/ui/Button.test.tsx
npm run test:watch
```

#### E2E Tests (Playwright)
```bash
npm run playwright:install   # first run only
npm run test:e2e
npm run test:e2e:ui
npm run test:e2e:headed
npm run test:e2e:report
```

#### Run All Tests
```bash
make test-all
# or
npm test && npm run test:e2e
```

#### E2E Coverage Overview
| Test Suite | Tests | Description |
|------------|-------|-------------|
| `home.spec.ts` | 5 | Home page, hero, features, navigation |
| `products.spec.ts` | 10 | Product listing, search, detail page |
| `cart.spec.ts` | 8 | Cart operations, checkout, empty state |
| `orders.spec.ts` | 9 | Orders list, detail, cancel, empty state |
| `navigation.spec.ts` | 10 | Routing, 404, responsive, accessibility |

### Docker
```bash
make docker-build
make docker-run
# or
docker build -t shopping-cart-frontend:v1.0.0 .
docker run -p 3000:80 shopping-cart-frontend:v1.0.0
```

### Kubernetes Deployment
```bash
helm lint helmchart -f ../config-secret-secure/values/local/20-frontend.yaml
helm upgrade --install frontend helmchart \
  --namespace shopping-cart-apps \
  -f ../config-secret-secure/values/local/20-frontend.yaml
```

### Development Workflow
#### Adding a New Page
1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Create API service if needed in `src/services/`
4. Add React Query hook in `src/hooks/`
5. Write tests

#### Adding a New UI Component
1. Create component in `src/components/ui/`
2. Export from component file
3. Write tests in the same directory

### State Management
- **Server State**: TanStack Query for fetching/caching
- **Client State**: Zustand for cart count and UI state
- **Form State**: Local component state (or React Hook Form as needed)

---

## Architecture
See **[Service Architecture](docs/architecture/README.md)** for tech stack rationale, auth flow, state management, and deployment details.

---

## Directory Layout
```
src/
├── components/
│   ├── layout/          # Layout components (Header, Footer, etc.)
│   └── ui/              # Reusable UI components (Button, Card, etc.)
├── config/              # Configuration (auth, API endpoints)
├── features/            # Feature-specific components
├── hooks/               # Custom React hooks (useProducts, useCart, etc.)
├── pages/               # Route page components
├── services/            # API service layer
├── stores/              # Zustand state stores
├── test/                # Test utilities
├── types/               # TypeScript type definitions
└── utils/               # Utility functions
```

---

## Documentation

### Architecture
- **[Service Architecture](docs/architecture/README.md)** — SPA structure, auth flow, state management, deployment.

### API Reference
- **[API Reference](docs/api/README.md)** — Backend endpoints, environment variables, and Axios patterns.

### Testing
- **[Testing Guide](docs/testing/README.md)** — Vitest + Playwright commands, coverage instructions, suites overview.

### Troubleshooting
- **[Troubleshooting Guide](docs/troubleshooting/README.md)** — Keycloak redirect fixes, proxy/CORS issues, env var gaps, Playwright setup tips.

### Issue Logs
- **[README + docs structure drift](docs/issues/2026-03-17-readme-standardization.md)** — Notes on the documentation realignment work.

---

## Releases

| Version | Date | Highlights |
|---------|------|------------|
| [v0.1.0](https://github.com/wilddog64/shopping-cart-frontend/releases/tag/v0.1.0) | 2026-03-14 | Initial React SPA release with Keycloak auth, cart/orders flows, Playwright coverage |

---

## Related
- [Platform Architecture](https://github.com/wilddog64/shopping-cart-infra/blob/main/docs/architecture.md)
- [shopping-cart-infra](https://github.com/wilddog64/shopping-cart-infra)
- [shopping-cart-order](https://github.com/wilddog64/shopping-cart-order)
- [shopping-cart-basket](https://github.com/wilddog64/shopping-cart-basket)
- [shopping-cart-payment](https://github.com/wilddog64/shopping-cart-payment)
- [shopping-cart-product-catalog](https://github.com/wilddog64/shopping-cart-product-catalog)

---

## License
Apache 2.0
