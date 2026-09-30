# Task Spec: Shopping Cart CI Stabilization — Round 2 Fixes

**Branch:** `fix/ci-stabilization` (already exists on all repos — push to existing branch)
**Agent:** Codex
**Priority:** Fix 1 first (unblocks Fix 3), then Fix 2, then Fix 3

---

## Context

Three CI failures remain after Round 1. This spec covers all three.
All changes go on the existing `fix/ci-stabilization` branch in each repo.
All PRs already exist — push additional commits to the existing PRs, do not open new ones.

**Do NOT touch:**
- Any logic outside of what is specified below
- Any file not listed in each fix section
- Do not add comments, refactor, or clean up surrounding code

**Do NOT update memory-bank until the PR CI is green.**
**Do NOT fabricate commit SHAs — only record real SHAs after the commit exists on GitHub.**

---

## Execution Order

Fix 1 first — rabbitmq-client-java publish job must run so the package is in GitHub Packages
before shopping-cart-order (Fix 3) can resolve the dependency.

1. Fix 1 — rabbitmq-client-java: unblock publish job
2. Fix 2 — shopping-cart-payment: add flyway-database-postgresql version
3. Fix 3 — shopping-cart-order: verify CI passes once package is published (no code change needed)

---

## Fix 1 — `rabbitmq-client-java` (publish job blocked)

**Repo:** `wilddog64/rabbitmq-client-java`
**Branch:** `fix/ci-stabilization`
**PR:** #1 (already open — push to this branch)

**Failure:** The `publish` job has `needs: [build, integration-test]` but `integration-test`
only runs on `push` to `main` — so on `fix/ci-stabilization` it is always skipped,
which causes `publish` to be skipped too.

**Fix:** In `.github/workflows/java-ci.yml`:

1. Change the `publish` job `needs` to only require `build` (remove `integration-test`):

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
```

2. The rest of the publish job steps remain unchanged.

**Only file to change:** `.github/workflows/java-ci.yml`

**Verify:** After push, the `Publish to GitHub Packages` job must show as running (not skipped)
in the Actions tab. Wait for it to complete before starting Fix 3.

---

## Fix 2 — `shopping-cart-payment` (flyway-database-postgresql missing version)

**Repo:** `wilddog64/shopping-cart-payment`
**Branch:** `fix/ci-stabilization`
**PR:** #1 (already open — push to this branch)

**Failure:** `pom.xml` line 68 — `flyway-database-postgresql` has no `<version>`.
Spring Boot 3.2.0 BOM does not manage this artifact.

**Fix:** In `pom.xml`, add an explicit version to `flyway-database-postgresql`:

```xml
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-database-postgresql</artifactId>
            <version>10.6.0</version>
        </dependency>
```

Flyway 10.6.0 is compatible with Spring Boot 3.2.x. Do not change any other dependency.

**Only file to change:** `pom.xml`

---

## Fix 3 — `shopping-cart-order` (rabbitmq-client unresolvable)

**Repo:** `wilddog64/shopping-cart-order`
**Branch:** `fix/ci-stabilization`
**PR:** #1 (already open)

**Failure:** `Could not find artifact com.shoppingcart:rabbitmq-client:jar:1.0.0-SNAPSHOT
in github-rabbitmq-client (https://maven.pkg.github.com/wilddog64/rabbitmq-client-java)`

This is a sequencing issue — the package is not yet published. After Fix 1 completes
and the `Publish to GitHub Packages` job succeeds in rabbitmq-client-java, re-run the
failing CI job in shopping-cart-order (use `gh run rerun` or push an empty commit).

**No code change needed** unless the CI still fails after the package is published,
in which case check the `maven-settings.xml` server ID matches the repository ID in pom.xml.

---

## Completion Criteria

- rabbitmq-client-java: `Publish to GitHub Packages` job green ✅
- shopping-cart-payment: `Build and Test` green ✅
- shopping-cart-order: `Build & Test` green ✅
- All changes on `fix/ci-stabilization` — no commits to `main`
- Update memory-bank ONLY after all three PRs are green
