# Task Spec: Shopping Cart CI Stabilization — Round 3 Fixes

**Branch:** `fix/ci-stabilization` (push to existing branch on each repo)
**Agent:** Codex
**PRs:** All PRs already exist — push additional commits, do not open new ones

---

## Context

Two repos remain failing after Round 2. One root cause is shared (GitHub Packages auth).
Fix in this order: payment first (simpler), then order (auth fix).

**Do NOT touch** anything outside the files listed per fix.
**Do NOT update memory-bank until both PRs are green.**
**Do NOT fabricate commit SHAs.**

---

## Fix 1 — `shopping-cart-payment`

**Repo:** `wilddog64/shopping-cart-payment`
**Branch:** `fix/ci-stabilization`
**PR:** #1 (push to existing branch)

**Two failures:**
1. `com.shoppingcart:rabbitmq-client:jar:1.0.0` — pom.xml has `<version>1.0.0</version>` but rabbitmq-client-java publishes `1.0.0-SNAPSHOT`
2. `com.paypal.sdk:checkout-sdk:jar:1.14.0` — Maven cannot resolve because GitHub Packages resolution fails fast and may cascade; also payment has no GitHub Packages repository declared

**Changes required:**

### `pom.xml` — three edits

**Edit 1:** Change `rabbitmq-client.version` property from `1.0.0` to `1.0.0-SNAPSHOT`:
```xml
<rabbitmq-client.version>1.0.0-SNAPSHOT</rabbitmq-client.version>
```

**Edit 2:** Add GitHub Packages repository with snapshots enabled (same as order).
Add inside `<project>`, after `</dependencies>`, before `<build>`:
```xml
    <repositories>
        <repository>
            <id>github-rabbitmq-client</id>
            <name>GitHub Packages — rabbitmq-client-java</name>
            <url>https://maven.pkg.github.com/wilddog64/rabbitmq-client-java</url>
            <snapshots>
                <enabled>true</enabled>
            </snapshots>
        </repository>
    </repositories>
```

### `.github/maven-settings.xml` — create new file

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

### `.github/workflows/ci.yaml` — two edits

**Edit 1:** Add `packages: read` permission to the `build` job:
```yaml
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: read
```

**Edit 2:** Pass maven-settings.xml and GITHUB_TOKEN to the build step.
Find the `./mvnw` or `mvn` build invocation and add `-s .github/maven-settings.xml` and env:
```yaml
      - name: Build and Test
        run: ./mvnw -B verify -s .github/maven-settings.xml
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**After push:** if `com.paypal.sdk:checkout-sdk` still fails after rabbitmq resolves,
add the following repository to `pom.xml` alongside the rabbitmq one:
```xml
        <repository>
            <id>paypal</id>
            <name>PayPal Maven Repository</name>
            <url>https://raw.github.com/paypal/SDK/maven</url>
        </repository>
```

---

## Fix 2 — `shopping-cart-order`

**Repo:** `wilddog64/shopping-cart-order`
**Branch:** `fix/ci-stabilization`
**PR:** #1 (push to existing branch)

**Failure:** `Could not find artifact com.shoppingcart:rabbitmq-client:jar:1.0.0-SNAPSHOT
in github-rabbitmq-client`

Codex already added `-s .github/maven-settings.xml` and `GITHUB_TOKEN` env, but the
workflow job is missing `packages: read` permission. GitHub Actions `GITHUB_TOKEN` does
not grant cross-repo package reads without an explicit permission declaration.

**Change required:**

### `.github/workflows/ci.yml` — one edit

Add `packages: read` permission to the build job that runs `mvn -B verify`:
```yaml
  build:
    name: Build & Test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: read
```

**Only file to change:** `.github/workflows/ci.yml`

---

## Completion Criteria

- payment: `Build and Test` green ✅
- order: `Build & Test` green ✅
- No changes to any other repo
- Update memory-bank ONLY after both PRs are green
