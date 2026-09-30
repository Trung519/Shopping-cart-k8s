# Issue: Multi-arch workflow pin update

**Date:** 2026-03-17
**Status:** Closed

## Summary
The CI workflow pinned to infra SHA `8363caf`, so Docker Buildx emitted amd64-only images. Infra SHA `999f8d7` adds `platforms: linux/amd64,linux/arm64` which is required for the arm64 Ubuntu k3s node.

## Fix
- Updated `.github/workflows/ci.yml` to reference `build-push-deploy.yml@999f8d70277b92d928412ff694852b05044dbb75`.

## Follow Up
- Monitor frontend CI to ensure multi-arch manifests push before rerunning ArgoCD sync.
