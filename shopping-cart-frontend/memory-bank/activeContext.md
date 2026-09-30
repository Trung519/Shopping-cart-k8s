# Active Context: Frontend (React/TypeScript)

## Current Status (2026-03-14)

CI green. All PRs merged to main. Branch protection active.

## What's Implemented

- React 18 + TypeScript + Vite SPA
- Pages: Home, Products, ProductDetail, Cart, Orders, Login, LoginCallback
- Keycloak OIDC integration (react-keycloak-web)
- Zustand cart store, React Query for data fetching
- Vitest + React Testing Library unit tests
- GitHub Actions CI: ESLint + TypeScript check + Vitest + Trivy + ghcr.io push

## CI History

- **fix/ci-stabilization PR #1** — merged 2026-03-14. Fixed: react-refresh lint warnings (targeted eslint-disable), vite/client types, tsconfig paths.
- **Branch protection** — 1 review + CI required, enforce_admins: false

## Active Task

- **Multi-arch workflow pin** — branch `fix/multiarch-workflow-pin` updates `.github/workflows/ci.yml` to reference infra SHA `999f8d7` (linux/amd64 + linux/arm64 images).
- **v0.1.0 release** — cut `release/v0.1.0` from main, add CHANGELOG, open PR, tag after merge.

## Agent Instructions

Rules that apply to ALL agents working in this repo:

1. **CI only** — do NOT run `npm run lint` or `npm test` locally without `npm install` first.
2. **Memory-bank discipline** — do NOT update until CI shows `completed success`.
3. **SHA verification** — verify commit SHA before reporting.
4. **Do NOT merge PRs** — open the PR and stop.

## Key Notes

- Node 20 required (`engines` field in package.json)
- `VITE_KEYCLOAK_URL` env var required for auth to work in local dev
