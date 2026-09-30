# Retrospective — PR #22 (RabbitMQ Connection Refused Fix)

**Date:** 2026-03-25
**Milestone:** Fix RabbitMQ "Connection refused" causing order-service CrashLoopBackOff
**PR:** #22 — merged to main (`7904c8a`)
**Participants:** Claude, Copilot

## What Went Well

- **Three root causes identified in one pass** — `loopback_users` restriction, missing ArgoCD app, and resource pressure were all found by reading across the infra repo before writing any code
- **Copilot caught a critical ArgoCD bug** — `path: data-layer` without `directory.recurse: true` would have synced an empty set; the fix would have appeared to work but nothing would have deployed
- **Copilot caught wrong config syntax** — `loopback_users.guest = none` is not a valid sysctl boolean; would have prevented RabbitMQ from starting entirely, masking the fix

## What Went Wrong

- **`none` used instead of `false` for boolean** — RabbitMQ sysctl format uses `true`/`false`, not string values; should have checked the official docs before writing the config value
- **ArgoCD recurse not set by default** — easy to miss; adding a data-layer ArgoCD app without `directory.recurse: true` is a silent no-op

## Process Rules Added

| Rule | Where |
|---|---|
| RabbitMQ sysctl booleans use `true`/`false`, not string values (`none`, `yes`, `no`) | RabbitMQ config checklist |
| ArgoCD Applications with `path:` pointing to a directory containing only subdirs must include `directory.recurse: true` | ArgoCD app template |
| Every data-layer component must have an ArgoCD Application — no component is "manually deployed" | Infra deployment checklist |

## Decisions Made

- **`loopback_users.guest = false` is dev-only** — Stage 2 Vault integration replaces `guest` entirely with dynamic credentials; this setting becomes irrelevant once Vault is in place
- **NetworkPolicy for cross-namespace RabbitMQ access** deferred to Stage 2 alongside Vault credentials — tracked as hardening item
- **Resource requests reduced to 200m/512Mi** — t3.medium (4GB) can't fit 500m/1Gi RabbitMQ alongside PostgreSQL, Redis, and app pods; limits remain at 1000m/1Gi to allow bursting

## Theme

A "Connection refused" from a remote pod that turned out to be three independent problems: RabbitMQ's `guest` user is localhost-only by default (a well-known gotcha that isn't obvious from the error message), the data-layer had no ArgoCD Application so RabbitMQ was never deployed after cluster resets, and resource requests were too high for the target node. Copilot caught two configuration correctness issues — wrong sysctl syntax and a missing ArgoCD recurse flag — that would have silently nullified the fix. All three are now fixed and documented.
