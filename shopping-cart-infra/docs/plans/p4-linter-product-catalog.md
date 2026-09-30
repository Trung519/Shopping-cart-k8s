# Spec: P4 Linter — shopping-cart-product-catalog (ruff + mypy)

**Date:** 2026-03-14
**Repo:** `wilddog64/shopping-cart-product-catalog`
**Branch:** create `feature/p4-linter` from main
**Assigned to:** Codex
**Working directory:** `/Users/cliang/src/gitrepo/personal/shopping-carts/shopping-cart-product-catalog`

---

## Background

Product-catalog is a Python 3.11 FastAPI service. Add `ruff` (linting + formatting) and
`mypy` (type checking) to CI.

---

## Changes Required

### 1. Add `[tool.ruff]` and `[tool.mypy]` to `pyproject.toml`

Add after the existing `[project]` sections:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "UP"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true
strict = false
warn_unused_ignores = true
```

### 2. Add `ruff` and `mypy` to dev dependencies in `pyproject.toml`

Find the `[project.optional-dependencies]` or `dev` extras section and add:

```toml
[project.optional-dependencies]
dev = [
    # existing entries...
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]
```

If no dev extras section exists, create it.

### 3. Add lint job to `.github/workflows/ci.yml`

Add a new `lint` job before `build`:

```yaml
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install lint tools
        run: pip install ruff mypy

      - name: Run ruff
        run: ruff check .

      - name: Run mypy
        run: mypy . --ignore-missing-imports
```

Update `build` job to add `needs: [lint]`:
```yaml
  build:
    name: Lint, Test & Build
    needs: [lint]
```

---

## Rules

- Do NOT modify source files to fix lint/type errors — report failures and stop
- Do NOT change the `publish` job
- First command: `hostname && uname -n`

---

## Completion Steps

1. Create branch `feature/p4-linter` from main
2. Apply changes to `pyproject.toml` and `.github/workflows/ci.yml`
3. Push to `feature/p4-linter` on `wilddog64/shopping-cart-product-catalog`
4. Open PR against main
5. Wait for CI: `gh run list --repo wilddog64/shopping-cart-product-catalog --branch feature/p4-linter`
6. If lint/type check fails: report failures and stop — do NOT fix source code
7. Verify SHA: `gh api repos/wilddog64/shopping-cart-product-catalog/git/commits/<sha>`
8. Update `wilddog64/shopping-cart-product-catalog/memory-bank/activeContext.md`
9. Do NOT update memory-bank until CI green (or lint failures documented)

---

## Completion Report Template

```
Repo: wilddog64/shopping-cart-product-catalog
Branch: feature/p4-linter
PR URL: <url>
Commit SHA (verified): <sha>
CI run ID: <run_id>
CI conclusion: success / failure
Ruff result: PASS / FAIL
Mypy result: PASS / FAIL
Files changed:
  - pyproject.toml — ruff + mypy config + dev deps added
  - .github/workflows/ci.yml — lint job added, build needs lint
```
