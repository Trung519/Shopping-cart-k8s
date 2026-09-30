# Task Spec: Shopping Cart CI Stabilization — P1 + P2

**Branch:** `fix/ci-stabilization` (already cut on all repos)
**Agent:** Codex
**Priority:** P1 first, then P2

---

## Context

Five shopping-cart service repos have failing CI. This spec covers all P1 and P2 fixes.
All changes go on the `fix/ci-stabilization` branch in each affected repo.
All PRs target `main`.

**Do NOT touch:**
- Any logic outside of what is specified below
- Any file not listed in each fix section
- Do not add comments, refactor, or clean up surrounding code

**Do NOT update memory-bank until the PR exists and CI is green.**
**Do NOT fabricate commit SHAs — only record real SHAs after the commit exists on GitHub.**

---

## P1 Fix 1 — `shopping-cart-frontend`

**Repo:** `wilddog64/shopping-cart-frontend`
**Branch:** `fix/ci-stabilization`
**Failure:** TypeScript `type-check` job — 9 errors in `tsc --noEmit`

### Exact errors from CI log

```
src/components/layout/Header.tsx(3,38): error TS6133: 'Package' is declared but its value is never read.
src/components/layout/ProtectedRoute.tsx(3,10): error TS6133: 'Navigate' is declared but its value is never read.
src/config/api.ts(2,34): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/config/api.ts(3,36): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/config/api.ts(4,33): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/config/auth.ts(4,34): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/config/auth.ts(5,36): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/config/auth.ts(6,31): error TS2339: Property 'env' does not exist on type 'ImportMeta'.
src/stores/cartStore.ts(3,21): error TS6196: 'CartItem' is declared but never used.
```

3 are unused import errors (Fixes A/B/C below).
6 are `ImportMeta.env` errors fixed by adding `vite/client` types (Fix D).

### Fix A — `src/components/layout/Header.tsx`

Current import line 3:
```ts
import { ShoppingCart, User, LogOut, Package } from 'lucide-react'
```
Change to:
```ts
import { ShoppingCart, User, LogOut } from 'lucide-react'
```

### Fix B — `src/components/layout/ProtectedRoute.tsx`

Current import line 3:
```ts
import { Navigate, useLocation } from 'react-router-dom'
```
Change to:
```ts
import { useLocation } from 'react-router-dom'
```

### Fix C — `src/stores/cartStore.ts`

Current import line 3:
```ts
import type { Cart, CartItem } from '@/types'
```
Change to:
```ts
import type { Cart } from '@/types'
```

### Fix D — `tsconfig.json`

Current `compilerOptions` has no `types` field. Add `"types": ["vite/client"]` after
the `"lib"` line. Do not change any other field.

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "types": ["vite/client"]
  }
}
```

### Commit message

```
fix: resolve TypeScript type-check errors blocking CI

- Remove unused Package import from Header.tsx
- Remove unused Navigate import from ProtectedRoute.tsx
- Remove unused CartItem type import from cartStore.ts
- Add "types": ["vite/client"] to tsconfig.json to fix ImportMeta.env errors
```

---

## P1 Fix 2 — `shopping-cart-product-catalog`

**Repo:** `wilddog64/shopping-cart-product-catalog`
**Branch:** `fix/ci-stabilization`
**Failure:** `Build, Scan & Push / build-push` — Trivy scan exits 1 on fixable HIGH/CRITICAL CVEs in `python:3.11-slim` base image

### Fix — `Dockerfile`

Add `RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*` immediately
after each `FROM` line in both stages — before any other RUN instruction.

**Builder stage** — insert immediately after `FROM python:3.11-slim as builder`:

```dockerfile
FROM python:3.11-slim as builder

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
```

**Runtime stage** — insert immediately after `FROM python:3.11-slim`:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 appuser
```

Do not change any other part of the Dockerfile.

### Commit message

```
fix: upgrade system packages in Docker image to resolve Trivy HIGH/CRITICAL CVEs

Add apt-get upgrade immediately after each FROM so all system packages
are patched before Trivy scan runs.
```

---

## P2 Fix 1 — `shopping-cart-payment`

**Repo:** `wilddog64/shopping-cart-payment`
**Branch:** `fix/ci-stabilization`
**Failure:** `Build and Test` job — `./mvnw` fails with:
`-Dmaven.multiModuleProjectDirectory system property is not set.`

### Fix — `.github/workflows/ci.yaml`

Add `-Dmaven.multiModuleProjectDirectory=.` to every `./mvnw` invocation.
There are 3 occurrences:

1. `run: ./mvnw clean package -DskipTests -B`
   → `run: ./mvnw clean package -DskipTests -B -Dmaven.multiModuleProjectDirectory=.`

2. `run: ./mvnw test -B`
   → `run: ./mvnw test -B -Dmaven.multiModuleProjectDirectory=.`

3. `run: ./mvnw verify -P integration-tests -B`
   → `run: ./mvnw verify -P integration-tests -B -Dmaven.multiModuleProjectDirectory=.`

### Commit message

```
fix: add -Dmaven.multiModuleProjectDirectory=. to mvnw invocations

Fixes "system property is not set" error when Maven wrapper initializes
in GitHub Actions environment.
```

---

## P2 Fix 2 — `rabbitmq-client-java` + `shopping-cart-order`

**Repos:** `wilddog64/rabbitmq-client-java` AND `wilddog64/shopping-cart-order`
**Branch:** `fix/ci-stabilization` on both repos
**Failure:** `shopping-cart-order` Build & Test fails:
`Could not find artifact com.shoppingcart:rabbitmq-client:jar:1.0.0-SNAPSHOT`

### Why the publish job must run on `fix/ci-stabilization`

The library must be published to GitHub Packages **before** `shopping-cart-order` CI can
resolve it. Since all fixes live on `fix/ci-stabilization`, the publish job must trigger
on pushes to that branch — not just `main`. Without this, `shopping-cart-order` CI will
remain broken throughout the fix branch work.

### Fix A — `rabbitmq-client-java`: add publish job to `.github/workflows/java-ci.yml`

Add a `publish` job after the existing `build` job. The `if` condition covers both
`fix/ci-stabilization` (for branch work) and `main` (for ongoing publishes):

```yaml
  publish:
    name: Publish to GitHub Packages
    runs-on: ubuntu-latest
    needs: [build]
    if: >
      github.event_name == 'push' &&
      (github.ref == 'refs/heads/main' ||
       github.ref == 'refs/heads/fix/ci-stabilization')
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: 'temurin'
          cache: maven

      - name: Publish to GitHub Packages
        run: mvn -B deploy -DskipTests -s .github/maven-settings.xml
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Fix B — `rabbitmq-client-java`: add `distributionManagement` to root `pom.xml`

Add inside the `<project>` element (after `<description>`):

```xml
    <distributionManagement>
        <repository>
            <id>github</id>
            <name>GitHub Packages</name>
            <url>https://maven.pkg.github.com/wilddog64/rabbitmq-client-java</url>
        </repository>
    </distributionManagement>
```

### Fix C — `rabbitmq-client-java`: add `.github/maven-settings.xml`

```xml
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">
  <servers>
    <server>
      <id>github</id>
      <username>${env.GITHUB_ACTOR}</username>
      <password>${env.GITHUB_TOKEN}</password>
    </server>
  </servers>
</settings>
```

### Fix D — `shopping-cart-order`: add GitHub Packages repository to `pom.xml`

```xml
    <repositories>
        <repository>
            <id>github-rabbitmq-client</id>
            <name>GitHub Packages — rabbitmq-client-java</name>
            <url>https://maven.pkg.github.com/wilddog64/rabbitmq-client-java</url>
        </repository>
    </repositories>
```

### Fix E — `shopping-cart-order`: add `.github/maven-settings.xml`

```xml
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">
  <servers>
    <server>
      <id>github-rabbitmq-client</id>
      <username>${env.GITHUB_ACTOR}</username>
      <password>${env.GITHUB_TOKEN}</password>
    </server>
  </servers>
</settings>
```

### Fix F — `shopping-cart-order`: update CI build step

In `.github/workflows/ci.yml`, update the build step to use the settings file:
```yaml
      - name: Build with Maven
        run: mvn -B verify -s .github/maven-settings.xml
```

### Commit messages

**rabbitmq-client-java:**
```
fix: add GitHub Packages publish job and distributionManagement

Publish job runs on fix/ci-stabilization and main so the library
is available while CI fix work is in progress.
```

**shopping-cart-order:**
```
fix: add GitHub Packages repository for rabbitmq-client dependency

Configures Maven to resolve com.shoppingcart:rabbitmq-client:1.0.0-SNAPSHOT
from wilddog64/rabbitmq-client-java GitHub Packages.
```

---

## Execution Order

1. **P2 Fix 2 first** — push `rabbitmq-client-java` fix to `fix/ci-stabilization` so the
   library publishes to GitHub Packages before `shopping-cart-order` CI runs
2. P1 fixes — `shopping-cart-frontend` and `shopping-cart-product-catalog` are independent
3. P2 Fix 1 — `shopping-cart-payment` is independent
4. `shopping-cart-order` — after `rabbitmq-client-java` package is visible in GitHub Packages
5. All PRs: `fix/ci-stabilization` → `main`

## Verification

After each fix is committed on `fix/ci-stabilization`:
- Run `gh pr create` targeting `main`
- Confirm CI passes on the PR before moving to the next repo
- Do NOT merge until CI is green
- Share PR URL — this is required proof of completion

## Memory-bank update

Only after all PRs are open and CI is green on each:
- Update `k3d-manager/memory-bank/progress.md` and `activeContext.md` on branch `k3d-manager-v0.9.0`
- Record real commit SHAs (verify each SHA exists via `gh api repos/.../git/commits/<sha>`)
- Record PR numbers
- Do NOT mark any item done until the PR CI is green
