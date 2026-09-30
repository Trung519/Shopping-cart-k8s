# Spec: P4 Linter — shopping-cart-basket (golangci-lint)

**Date:** 2026-03-14
**Repo:** `wilddog64/shopping-cart-basket`
**Branch:** create `feature/p4-linter` from main
**Assigned to:** Codex
**Working directory:** `/Users/cliang/src/gitrepo/personal/shopping-carts/shopping-cart-basket`

---

## Background

All 5 service CI PRs are merged. Branch protection is active (1 review + CI required).
Next step: add linters so code quality is enforced on every PR.

Basket is written in Go 1.21. Add `golangci-lint` to CI.

---

## Changes Required

### 1. Add `.golangci.yml` (new file at repo root)

```yaml
run:
  timeout: 5m

linters:
  enable:
    - govet
    - errcheck
    - staticcheck
    - gosimple
    - ineffassign
    - unused
    - gofmt
    - goimports

linters-settings:
  gofmt:
    simplify: true

issues:
  max-issues-per-linter: 50
  max-same-issues: 10
```

### 2. Add lint job to `.github/workflows/go-ci.yml`

Add a new `lint` job **before** the `test` job (does not depend on test):

```yaml
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'
      - name: Run golangci-lint
        uses: golangci/golangci-lint-action@v6
        with:
          version: v1.57.2
```

Update `test` job to add `needs: [lint]`:
```yaml
  test:
    name: Test
    needs: [lint]
    runs-on: ubuntu-latest
```

---

## Rules

- Do NOT modify any Go source files to fix lint issues — if lint fails, report the failures and stop. Do not auto-fix.
- Do NOT change the `publish` job
- Do NOT use `@latest` for golangci-lint-action — pin to `@v6`
- First command: `hostname && uname -n`

---

## Completion Steps

1. Create branch `feature/p4-linter` from main
2. Add `.golangci.yml` and update `.github/workflows/go-ci.yml`
3. Push to `feature/p4-linter` on `wilddog64/shopping-cart-basket`
4. Open PR against main
5. Wait for `gh run list --repo wilddog64/shopping-cart-basket --branch feature/p4-linter` → `completed success`
6. If lint fails due to existing issues: report the failures in the completion report and stop — do NOT fix source code
7. Verify commit SHA: `gh api repos/wilddog64/shopping-cart-basket/git/commits/<sha>`
8. Update `wilddog64/shopping-cart-basket/memory-bank/activeContext.md` with PR URL, run ID, verified SHA
9. Do NOT update memory-bank until CI shows `completed success` (or until lint failures are documented if step 6 applies)

---

## Completion Report Template

```
Repo: wilddog64/shopping-cart-basket
Branch: feature/p4-linter
PR URL: <url>
Commit SHA (verified): <sha>
CI run ID: <run_id>
CI conclusion: success / failure
Lint result: PASS / FAIL (list failures if any)
Files changed:
  - .golangci.yml — created
  - .github/workflows/go-ci.yml — lint job added, test needs lint
```
