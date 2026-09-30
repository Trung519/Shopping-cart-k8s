# Project Brief: Shopping Cart Frontend

## What This Project Does

Shopping Cart Frontend is a React-based single-page application (SPA) that serves as the user interface for the Shopping Cart microservices platform. It allows users to:

- Browse and search a product catalog
- View product details and pricing
- Add products to a shopping cart and manage quantities
- Authenticate via Keycloak SSO (OAuth2/OIDC)
- Place orders and view order history with status tracking

## Goals

- Provide a responsive, mobile-first shopping experience
- Integrate seamlessly with three backend microservices (Product Catalog, Basket, Order)
- Enforce authentication for cart and order pages via Keycloak
- Be deployable as a Docker container into Kubernetes with zero-configuration service discovery via nginx proxying

## Scope

**In scope:**
- Product browsing (listing, search/filter by category, pagination, detail view)
- Shopping cart (add, update quantity, remove items, real-time totals)
- Order management (create order at checkout, view history, view details, cancel)
- OAuth2/OIDC authentication and protected routes
- Responsive UI with Tailwind CSS
- Unit tests for components and utilities
- Playwright E2E tests for all major user flows
- Docker + Kubernetes deployment manifests

**Out of scope:**
- Payment processing UI (handled by Payment Service)
- Admin/back-office screens
- Direct database access
- Real-time WebSocket updates

## Project Position in the Platform

This frontend is one of 5 repositories in the Shopping Cart platform:

| Repository | Role |
|---|---|
| `shopping-cart-frontend` (this repo) | React SPA — user interface |
| `shopping-cart-product-catalog` | Python/FastAPI — product data |
| `shopping-cart-basket` | Go/Gin — cart sessions (Redis) |
| `shopping-cart-order` | Java/Spring Boot — order processing |
| `shopping-cart-infra` | Kubernetes infrastructure + GitOps |

## Target Users

End users of the shopping platform — anonymous users can browse products; authenticated users can manage carts and orders.

## Key Constraints

- All environment-specific configuration injected at build time via `VITE_*` environment variables
- Backend service URLs proxied through nginx at runtime — the SPA never makes cross-origin requests
- Authentication is strictly via Keycloak; no custom user database in this service
- Node.js 20+ required for development
