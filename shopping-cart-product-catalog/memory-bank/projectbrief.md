# Project Brief: Product Catalog Service

## What This Project Does

The Product Catalog Service is a Python/FastAPI microservice that manages the product inventory and catalog for the Shopping Cart platform. It serves as the authoritative source for product information (name, SKU, price, description, category) and inventory quantities, and publishes inventory change events to RabbitMQ for other services to react to.

## Core Responsibilities

- **Product CRUD**: Create, read, update, and soft-delete products with SKU-based deduplication
- **Inventory management**: Track product quantities, apply inventory changes (positive or negative deltas), and detect low-stock conditions
- **Product search and filtering**: List products with pagination, category filtering, and active-only filtering
- **Event publishing**: Publish RabbitMQ events when inventory changes (`inventory.updated`, `inventory.low`, `inventory.reserved`) for downstream services (Order Service for fulfillment, notification services)
- **Product catalog serving**: Provide product details that the Basket Service client uses when adding items to cart

## Goals

- Provide a fast, reliable product and inventory management API
- Enable event-driven inventory tracking across the platform
- Support high read-to-write ratio with efficient querying (indexed SKU, category, is_active)
- Enforce soft deletes to preserve historical references

## Scope

**In scope:**
- Product CRUD (create, read, update, soft-delete)
- Inventory quantity tracking and adjustment
- Product listing with pagination and filtering
- Lookup by ID and by SKU
- RabbitMQ event publishing for inventory changes
- JWT authentication via Keycloak (optional, configurable)
- Prometheus metrics
- Structured JSON logging
- Security headers and rate limiting middleware
- Kubernetes deployment with ArgoCD

**Out of scope:**
- Shopping cart management (shopping-cart-basket service)
- Order processing (shopping-cart-order service)
- Payment processing (shopping-cart-payment service)
- Category hierarchy management (mentioned in architecture docs but not implemented in current model — single flat `category` string field in the Product model)
- Product search/full-text search
- Product images (image_url field stored but not managed)
- Multi-currency pricing (currency field stored but single price)

## Service Context in the Platform

The Product Catalog Service is upstream of both the Basket Service (which reads product details to populate cart items) and the Order Service (which needs inventory reservation confirmation). It publishes inventory events that allow the Order Service to track fulfillment. The Basket Service does NOT call the Product Catalog API synchronously — product details are passed by the client when adding to cart.

## Status

Active development. Core product model and FastAPI application structure are in place. Security and auth tests are implemented. The architecture docs reference a more complex structure (services, repositories, categories) than what is currently implemented in the flat source layout.
