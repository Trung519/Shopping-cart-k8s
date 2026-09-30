# Spec: Fix Frontend ESLint Lint Warnings — shopping-cart-frontend

**Date:** 2026-03-14
**Repo:** `wilddog64/shopping-cart-frontend`
**Branch:** `fix/ci-stabilization`
**Failing run:** `23064411684`
**Assigned to:** Codex

---

## Background

CI lint job fails with 4 `react-refresh/only-export-components` warnings. The ESLint config
sets `--max-warnings 0` so any warning is a build failure.

These are legitimate code patterns — not bugs. The fix is targeted `eslint-disable` inline
comments, not restructuring the files.

---

## Exact Errors

```
src/components/ui/Badge.tsx:32:17   — exports badgeVariants (non-component) alongside Badge
src/components/ui/Button.tsx:55:18  — exports buttonVariants (non-component) alongside Button
src/test/test-utils.tsx:18:10       — exports Wrapper component + non-component function
src/test/test-utils.tsx:30:1        — export * from '@testing-library/react'
```

---

## Fix 1 — `src/components/ui/Badge.tsx`

Add disable comment on the export line (line 32):

```tsx
// eslint-disable-next-line react-refresh/only-export-components
export { Badge, badgeVariants }
```

## Fix 2 — `src/components/ui/Button.tsx`

Add disable comment on the export line (line 55):

```tsx
// eslint-disable-next-line react-refresh/only-export-components
export { Button, buttonVariants }
```

## Fix 3 — `src/test/test-utils.tsx`

Add a file-level disable at the top of the file (line 1) — this file is test infrastructure,
not a component, and will always mix exports:

```tsx
/* eslint-disable react-refresh/only-export-components */
```

---

## Rules

- Touch only the three files listed above
- Do NOT restructure the files or move exports to separate files
- Do NOT modify ESLint config or `package.json`
- Do NOT change `--max-warnings 0` in the lint script
- First command: `hostname && uname -n`

---

## Completion Steps

1. Apply the three fixes above
2. Push to `fix/ci-stabilization` on `wilddog64/shopping-cart-frontend`
3. Run `gh run list --repo wilddog64/shopping-cart-frontend --branch fix/ci-stabilization` and wait for `completed	success`
4. Verify commit SHA: `gh api repos/wilddog64/shopping-cart-frontend/git/commits/<sha>`
5. Update `wilddog64/shopping-cart-frontend/memory-bank/activeContext.md` with green run ID and verified SHA
6. Do NOT update memory-bank until CI shows `completed	success`

---

## Completion Report Template

```
Repo: wilddog64/shopping-cart-frontend
Branch: fix/ci-stabilization
Commit SHA (verified): <sha>
CI run ID: <run_id>
CI conclusion: success
Files changed:
  - src/components/ui/Badge.tsx — eslint-disable-next-line added line 32
  - src/components/ui/Button.tsx — eslint-disable-next-line added line 55
  - src/test/test-utils.tsx — file-level eslint-disable added line 1
```
