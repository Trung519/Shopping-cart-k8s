# Issue: README + docs structure drift

**Date:** 2026-03-17
**Status:** Closed

## Summary
The frontend repository diverged from the standardized documentation structure adopted across the Shopping Cart apps. README mixed architecture, API, testing, and troubleshooting content inline, and the `docs/` hierarchy was missing entirely.

## Impact
- Operators could not rely on consistent locations for architecture/API/testing references.
- Issue history could not be tracked within the repo (`docs/issues/` absent).
- Future automation that expects `docs/*/README.md` placeholders would fail.

## Resolution
- Added `docs/architecture`, `docs/api`, `docs/testing`, and `docs/troubleshooting` with curated content synced from the existing README.
- Created `docs/issues/` with `.gitkeep` and logged this task for traceability.
- Rewrote the root `README.md` to follow the shared template (Quick Start, Usage, Architecture link, Directory Layout, Documentation index, Releases, Related links).

## Follow Up
- Repeat the same standardization in the remaining Shopping Cart service repos (basket, order, payment, product-catalog).
- Keep new docs updated whenever service architecture or APIs change.
