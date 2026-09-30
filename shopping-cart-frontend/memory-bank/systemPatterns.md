# System Patterns: Shopping Cart Frontend

## Application Entry Point

`src/main.tsx` bootstraps the app with a fixed provider hierarchy:

```
React.StrictMode
  └── AuthProvider (react-oidc-context, reads oidcConfig)
        └── QueryClientProvider (TanStack Query, staleTime 5min, retry 1)
              └── BrowserRouter (React Router)
                    └── App (routes)
```

The order matters: Auth must wrap Query so that hooks can access tokens; Router must wrap App for routing context.

## Routing Architecture

All routes are defined declaratively in `src/App.tsx`. The `Layout` component wraps all routes except `/callback`, providing the shared Header/Footer shell.

```
/callback          → LoginCallback (OIDC redirect handler)
/ (Layout shell)
  /                → HomePage (public)
  /products        → ProductsPage (public)
  /products/:id    → ProductDetailPage (public)
  /cart            → ProtectedRoute → CartPage
  /orders          → ProtectedRoute → OrdersPage
  /orders/:id      → ProtectedRoute → OrderDetailPage
  /*               → NotFoundPage
```

`ProtectedRoute` checks `auth.isAuthenticated`. If false, it calls `auth.signinRedirect()` to redirect to Keycloak. During auth loading, `App` renders a full-screen `LoadingSpinner`.

## Authentication Pattern

Authentication flow:
1. User clicks Login in Header → `auth.signinRedirect()` → browser redirects to Keycloak
2. Keycloak authenticates user → redirects to `http://localhost:3000/callback?code=...`
3. `LoginCallback` page (or OIDC library) exchanges code for tokens
4. `onSigninCallback` strips code/state from URL via `window.history.replaceState`
5. Tokens stored in localStorage under `oidc.user:<authority>:<clientId>`

Token injection in API calls:
- `src/services/api.ts` creates an Axios instance
- A request interceptor reads the token via `getAccessToken()` and sets `Authorization: Bearer <token>` header
- All service functions use this shared Axios instance

## Data Fetching Pattern (TanStack Query)

All server data lives in React Query. Hooks in `src/hooks/` are thin wrappers:

```typescript
// Pattern used for all data hooks
export function useProducts(params?: ProductQueryParams) {
  return useQuery({
    queryKey: ['products', params],   // Cache key includes params for per-query caching
    queryFn: () => productService.getProducts(params),
  })
}
```

Query key conventions:
- `['products']` — all products
- `['products', params]` — filtered/paginated products
- `['products', id]` — single product
- `['cart']` — current user's cart
- `['orders']` — orders list
- `['orders', id]` — single order

Mutations use `useMutation` and manually `queryClient.invalidateQueries()` on success to refresh stale data.

## Client State Pattern (Zustand)

The cart store (`src/stores/cartStore.ts`) manages:
- `cart`: full cart data from the last API response (not persisted)
- `itemCount`: count of items for the header badge (persisted to localStorage as `cart-storage`)

Only `itemCount` is partitioned for persistence — full cart data is always re-fetched on page load.

```typescript
// The store exposes only synchronous state setters
setCart(cart)         // Sets cart data and recalculates itemCount
setLoading(bool)      // Loading state
setError(string|null) // Error state
clearCart()           // Resets cart and itemCount to zero
```

## Component Architecture

### UI Component Pattern
Reusable UI components in `src/components/ui/` follow this pattern:
1. Define variants with `cva()` (class-variance-authority)
2. Accept `className` prop for override merging via `cn()`
3. Forward refs where relevant (input, button)
4. Export a `variantName` const in addition to the component for composability

Example (`Button.tsx`):
```typescript
const buttonVariants = cva('inline-flex items-center...', {
  variants: { variant: { default: '...', outline: '...' }, size: { sm: '...', default: '...', lg: '...' } },
  defaultVariants: { variant: 'default', size: 'default' },
})
export function Button({ className, variant, size, ...props }) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
}
```

### Layout Components
- `Layout`: renders `<Header>` + `<Outlet>` + `<Footer>` (React Router layout route)
- `Header`: shows logo, nav links, cart badge (reads `itemCount` from Zustand), Login/Logout button
- `ProtectedRoute`: authentication guard wrapper component

## Service Layer Pattern

Service functions in `src/services/` are plain async functions that use the shared Axios instance:

```typescript
// All service files export named async functions
export const productService = {
  getProducts: (params) => api.get('/api/products', { params }).then(r => r.data),
  getProductById: (id) => api.get(`/api/products/${id}`).then(r => r.data),
}
```

The base `api.ts` Axios instance:
- `baseURL` is empty (all paths are absolute)
- Request interceptor: injects Bearer token
- Response interceptor: (currently none — errors are handled per-hook)

## Type System

All TypeScript interfaces are centralized in `src/types/index.ts`:
- `Product`, `ProductCategory`
- `Cart`, `CartItem`, `AddToCartRequest`, `UpdateCartItemRequest`
- `Order`, `OrderItem`, `OrderStatus` (union type), `Address`
- `ApiError`, `PaginatedResponse<T>` (generic)
- `User`

This single-file approach ensures consistency between service responses and component props.

## Testing Patterns

### Unit test structure
```typescript
import { renderWithProviders } from '@/test/test-utils'

describe('ComponentName', () => {
  it('renders correctly', () => {
    const { getByText } = renderWithProviders(<Component />)
    expect(getByText('...')).toBeInTheDocument()
  })
})
```

`renderWithProviders` wraps in all required context providers so individual component tests don't need to set up QueryClient, AuthProvider, or Router.

### E2E test structure (Playwright in `e2e/`)
- `home.spec.ts` — home page content and navigation
- `products.spec.ts` — product listing, search, detail page
- `cart.spec.ts` — cart operations, checkout, empty state
- `orders.spec.ts` — orders list, detail view, cancel
- `navigation.spec.ts` — routing, 404, responsive, accessibility

Playwright config (`playwright.config.ts`) uses `baseURL: http://localhost:3000`.
