# Issue: Multi-arch workflow pin update

**Date:** 2026-03-17
**Status:** Closed

## Summary
`.github/workflows/ci.yml` was pinned to infra SHA `8363caf`, so CI only produced amd64 images. Need to reference SHA `999f8d7` that enables linux/amd64 and linux/arm64 builds.

## Fix
- Updated reusable workflow reference to `build-push-deploy.yml@999f8d70277b92d928412ff694852b05044dbb75`.
- Ensures ghcr publishes both architectures, unblocking arm64 k3s nodes.

## Follow Up
- Watch next CI run to confirm multi-arch manifests push successfully.
