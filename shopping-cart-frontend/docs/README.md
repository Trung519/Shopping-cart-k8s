# Shopping Cart Frontend — Documentation

## Contents

- [Architecture](architecture/README.md) — component structure, state management, auth flow
- [API](api/README.md) — backend service contracts and endpoint reference
- [Testing](testing/README.md) — unit and integration test guide
- [Troubleshooting](troubleshooting/README.md) — common issues and fixes

## Overview

React 18 + TypeScript SPA. Authenticates via Keycloak OIDC, communicates with three backend
services (Order, Product Catalog, Basket) via nginx reverse proxy (dev: Vite proxy).

See the root [README](../README.md) for quick-start, environment variables, and available scripts.
