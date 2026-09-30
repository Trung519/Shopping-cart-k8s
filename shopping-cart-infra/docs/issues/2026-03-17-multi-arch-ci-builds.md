# Issue: amd64-only images fail on arm64 k3s node

**Date:** 2026-03-17
**Status:** Open
**Assigned:** Codex
**Branch:** `fix/multi-arch-ci-builds` (create new, base off main)

## Problem

The Ubuntu Parallels VM running k3s is `arm64`. All 5 shopping-cart CI pipelines build
`linux/amd64`-only images. When ArgoCD deploys these to the arm64 node, pods fail with
`exec format error`.

Gemini identified this during ArgoCD verification (2026-03-17). The 401 Unauthorized issue
was fixed separately via `ghcr-pull-secret` patch (`fix/argocd-image-pull` branch). This
issue covers the remaining arch mismatch blocker.

## Root Cause

`build-push-deploy.yml` (the shared reusable workflow called by all 5 repos) uses
`docker/build-push-action@v5` without a `platforms` argument. Docker Buildx defaults to
the runner's native platform (`linux/amd64`).

## Fix — single file change

**File:** `.github/workflows/build-push-deploy.yml` in `shopping-cart-infra`

The workflow has two `docker/build-push-action@v5` steps:

1. **"Build image"** (`push: false`, `load: true`) — used for Trivy scan. Keep as-is.
   `load: true` is incompatible with multi-platform builds. Trivy only needs amd64.

2. **"Push image"** (`push: true`) — add `platforms: linux/amd64,linux/arm64`.

```yaml
      - name: Push image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64    # ADD THIS LINE
          tags: |
            ${{ inputs.image-name }}:sha-${{ github.sha }}
            ${{ inputs.image-name }}:latest
          cache-from: type=gha
          secrets: |
            GH_TOKEN=${{ secrets.PACKAGES_TOKEN }}
```

`docker/setup-buildx-action@v3` is already present — no additional setup required.

## Acceptance Criteria

- [ ] `platforms: linux/amd64,linux/arm64` added to the "Push image" step only
- [ ] "Build image" step (`load: true`) unchanged
- [ ] No other files modified
- [ ] Commit on `fix/multi-arch-ci-builds` branch in `shopping-cart-infra`
- [ ] Commit message: `fix: add linux/arm64 to push step in build-push-deploy workflow`
- [ ] SHA reported back — do NOT update memory-bank

## Verification (Claude does this after Codex reports done)

```bash
git show <sha> --stat   # must show only build-push-deploy.yml changed
git show <sha> | grep "platforms"  # must show + platforms: linux/amd64,linux/arm64
```

After merge + re-trigger of all 5 repo CI pipelines, Gemini re-verifies ArgoCD pods
Running on arm64 node.
