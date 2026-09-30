# Shopping Cart Frontend — Testing Guide

## Overview
This project ships both unit tests (Vitest + React Testing Library) and browser-based end-to-end tests (Playwright). Use the Makefile helpers or npm scripts below to exercise suites locally or in CI.

## Prerequisites
- Node.js 20+
- npm 10+
- For E2E tests: Playwright browsers installed via `npm run playwright:install`
- Backend + Keycloak services available for authenticated flows during E2E runs

## Unit Tests (Vitest)
```bash
# Run entire suite
npm test

# Watch mode for iterative development
npm run test:watch

# Generate coverage report (outputs to coverage/)
npm run test:coverage

# Target a single spec
npm test -- src/components/ui/Button.test.tsx
```
Focus areas include UI components, Zustand stores, and utility helpers. Shared setup utilities live in `src/test/`.

## End-to-End Tests (Playwright)
```bash
# Install browsers (first run only)
npm run playwright:install

# Headless run used in CI
npm run test:e2e

# Run with UI viewer for debugging
npm run test:e2e:ui

# Run headed for a single browser
npm run test:e2e:headed

# Generate HTML report
npm run test:e2e:report
```
Suites live in `e2e/`:
- `home.spec.ts` — hero, CTA, navigation smoke tests
- `products.spec.ts` — catalog listing, filters, product detail
- `cart.spec.ts` — add/update/remove items, checkout
- `orders.spec.ts` — order history, drilling into details
- `navigation.spec.ts` — routing, 404 screen, responsive menu behaviors

## Combined Test Execution
Use the Makefile helper to run both suites sequentially:
```bash
make test-all
```
This executes `npm test` followed by `npm run test:e2e` and matches the CI workflow.
