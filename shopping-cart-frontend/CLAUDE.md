# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Shopping Cart Frontend** is a React-based single-page application for the Shopping Cart platform. It provides product browsing, cart management, and order tracking with OAuth2/OIDC authentication via Keycloak.

## Technology Stack

- **React 18** with TypeScript
- **Vite 5** for build tooling
- **TanStack Query** for server state
- **Zustand** for client state
- **React Router 6** for routing
- **Tailwind CSS** for styling
- **Vitest** + React Testing Library for testing

## Common Commands

```bash
# Development
npm run dev           # Start dev server on port 3000
npm run build         # Build for production
npm run preview       # Preview production build

# Testing
npm test              # Run tests
npm run test:watch    # Watch mode
npm run test:coverage # With coverage

# Quality
npm run lint          # ESLint
npm run format        # Prettier
```

## Project Structure

```
src/
├── components/
│   ├── layout/       # Layout (Header, Footer, ProtectedRoute)
│   └── ui/           # Reusable components (Button, Card, Input, Badge)
├── config/           # Auth and API configuration
├── hooks/            # React Query hooks (useProducts, useCart, useOrders)
├── pages/            # Route pages
├── services/         # API client and service functions
├── stores/           # Zustand stores (cartStore)
├── test/             # Test utilities
├── types/            # TypeScript types
└── utils/            # Utility functions (cn, format)
```

## Key Patterns

### Authentication

Authentication uses `react-oidc-context` with Keycloak:

```typescript
// src/config/auth.ts - OIDC configuration
// src/components/layout/ProtectedRoute.tsx - Route protection
// src/services/api.ts - Axios interceptor adds Bearer token
```

### Data Fetching

Uses TanStack Query for server state:

```typescript
// Hooks pattern in src/hooks/
export function useProducts(params) {
  return useQuery({
    queryKey: ['products', params],
    queryFn: () => productService.getProducts(params),
  })
}
```

### State Management

Client state uses Zustand with persistence:

```typescript
// src/stores/cartStore.ts
export const useCartStore = create(
  persist(
    (set, get) => ({
      cart: null,
      itemCount: 0,
      setCart: (cart) => { ... },
    }),
    { name: 'cart-storage' }
  )
)
```

### Component Patterns

UI components use class-variance-authority for variants:

```typescript
// src/components/ui/Button.tsx
const buttonVariants = cva('...base classes...', {
  variants: {
    variant: { default: '...', outline: '...' },
    size: { sm: '...', default: '...', lg: '...' },
  },
})
```

## Environment Variables

All prefixed with `VITE_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_KEYCLOAK_URL` | `http://localhost:8080` | Keycloak server URL |
| `VITE_KEYCLOAK_REALM` | `shopping-cart` | Keycloak realm |
| `VITE_CLIENT_ID` | `frontend` | OAuth2 client ID |
| `VITE_ORDER_SERVICE_URL` | `/api/orders` | Order API endpoint |
| `VITE_PRODUCT_SERVICE_URL` | `/api/products` | Product API endpoint |
| `VITE_CART_SERVICE_URL` | `/api/cart` | Cart API endpoint |

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Main app with routing |
| `src/main.tsx` | Entry point with providers |
| `src/config/auth.ts` | Keycloak OIDC config |
| `src/config/api.ts` | API endpoint config |
| `src/services/api.ts` | Axios instance with auth |
| `src/stores/cartStore.ts` | Cart state management |
| `src/components/layout/ProtectedRoute.tsx` | Auth route guard |

## Testing

Tests are colocated with components:

```
src/components/ui/Button.tsx
src/components/ui/Button.test.tsx
```

Test utilities in `src/test/`:
- `setup.ts` - Global test setup
- `test-utils.tsx` - Custom render with providers

## API Integration

Services in `src/services/`:

```typescript
// productService.ts - getProducts(), getProductById()
// cartService.ts - getCart(), addItem(), checkout()
// orderService.ts - getOrders(), getOrderById()
```

All use the base `api.ts` Axios instance which handles auth tokens.

## Docker & Kubernetes

```bash
# Build image
docker build -t shopping-cart/frontend:latest .

# Deploy to K8s
kubectl apply -k k8s/base
```

The nginx config proxies `/api/*` requests to backend services.

## Common Tasks

### Add a new page

1. Create `src/pages/NewPage.tsx`
2. Add route in `src/App.tsx`
3. Wrap with `<ProtectedRoute>` if auth required

### Add a new API endpoint

1. Add endpoint to `src/config/api.ts`
2. Add service function in `src/services/`
3. Create React Query hook in `src/hooks/`

### Add a new UI component

1. Create in `src/components/ui/`
2. Use `cn()` for class merging
3. Use `cva()` for variants
4. Write tests

## Code Style

- Functional components with hooks
- TypeScript strict mode
- Named exports (except pages)
- Tailwind for styling
- Prettier for formatting

## Related Services

| Service | Port | API Prefix |
|---------|------|------------|
| Order Service | 8081 | `/api/orders` |
| Product Catalog | 8082 | `/api/products` |
| Basket Service | 8083 | `/api/cart` |
| Keycloak | 8080 | `/realms/shopping-cart` |
