# Retrospective — PR #23 — ESO apiVersion fix + CI bootstrap

**Date:** 2026-04-04
**Milestone:** ESO v1beta1 → v1 + validate CI workflow
**PR:** #23 — merged to main (`0a38037`)
**Participants:** Claude, Codex, Gemini, Copilot

## What Went Well

- **Root cause discovery was fast** — Gemini's live cluster investigation identified the ESO apiVersion mismatch within one session, unblocking the entire app layer
- **Codex execution was clean** — 8-file apiVersion replace done correctly in one commit, zero scope creep
- **CI bootstrapped in the same PR** — yamllint + kubeconform + kustomize-build now gate every future PR; kubeconform and kustomize-build passed on the first run
- **Copilot caught 6 real issues** — namespace ownership gaps, stale comment references, CHANGELOG value error (`none` vs `false`), misleading PR description; all legitimate findings
- **ArgoCD re-registration** — Gemini correctly identified that the 15-day-old stale cluster secret was blocking app sync; re-registration unblocked all app deployments

## What Went Wrong

- **yamllint required 3 iterations** — indentation config needed two fixup commits before CI went green; pre-existing manifest debt caused false failures
- **`secrets` namespace ownership not documented** — Copilot correctly flagged that `vault-bridge` and `ClusterSecretStore` depend on a namespace created by k3d-manager, not this repo; should have been commented from the start
- **Step 10 of `make up` silently left stale ArgoCD token** — the `namespaces "cicd" not found` error was logged but not fatal; old cluster secret persisted for 15 days undetected

## Process Rules Added

| Rule | Where |
|------|--------|
| Any manifest in `secrets` ns must note that k3d-manager owns the namespace | `data-layer/secrets/*.yaml` comment pattern |
| `bin/acg-up` Step 10 must verify the cluster secret was actually updated (not stale) | k3d-manager acg-up spec for next session |

## Decisions Made

- **ESO apiVersion `v1` (not `v1beta1`)** — ESO 0.9.20 on k3s serves `v1`; all manifests updated to match; do not revert to `v1beta1`
- **yamllint `indentation: disable`** — pre-existing manifest indentation debt is not worth fixing; kubeconform handles structural correctness; yamllint focuses on syntax and truthy values only
- **CI workflow `validate.yml` is infra-only** — does not replace `build-push-deploy.yml`; focuses on YAML correctness for manifests, not app builds

## Theme

This PR fixed the last infrastructure blocker preventing shopping-cart app pods from running on the remote k3s cluster. The ESO apiVersion mismatch was invisible until Gemini ran live `kubectl` commands and found no pods deployed. Codex fixed it in one clean commit. The same PR bootstrapped CI for the repo — previously there was no validation gate on manifest changes. Copilot's review caught namespace ownership gaps that could cause future confusion when someone applies these manifests to a fresh cluster without k3d-manager context.
