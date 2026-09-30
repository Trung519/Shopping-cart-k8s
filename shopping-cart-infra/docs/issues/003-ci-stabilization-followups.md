# Issue 003 — CI Stabilization Follow-ups

## Summary

During the March 2026 CI stabilization pass, the required code changes were
committed across all service repositories. Two items could not be validated
locally from the macOS runner due to tooling constraints:

1. `shopping-cart-frontend` `npm run build` still fails because the current
   `vite.config.ts` includes a `test` property that Vite's config typings do not
   recognise. The TS errors that were blocking CI (missing `vite/client` types
   and unused imports) are resolved, but the existing Vite config still needs to
   be updated separately.
2. Maven-based services (`shopping-cart-payment`, `rabbitmq-client-java`,
   `shopping-cart-order`) initially could not be verified locally because the
   Mac host lacked Maven. After installing Homebrew `maven` and exporting
   `JAVA_HOME=/opt/homebrew/opt/openjdk`, the builds now run but expose separate
   upstream issues:
   - `shopping-cart-payment`: `mvn clean package -DskipTests` fails with
     `'dependencies.dependency.version' for org.flywaydb:flyway-database-postgresql:jar is missing`
     (existing POM bug).
   - `rabbitmq-client-java`: `mvn clean install -DskipTests` fails with
     `java.lang.ExceptionInInitializerError: com.sun.tools.javac.code.TypeTag :: UNKNOWN`
     when compiling Lombok sources under OpenJDK 25.
   - `shopping-cart-order`: build still depends on the client library publishing
     successfully; until the above issues are resolved, local `mvn verify` cannot
     complete.

## Reproduction

### Frontend
```
npm install
npm run build  # fails with TS2769 in vite.config.ts ("test" property)
```

### Maven-based services
```
# mvn / mvnw unavailable on local macOS host
./mvnw clean package  # hangs while downloading wrapper
```

## Next Steps

- Update `vite.config.ts` in `shopping-cart-frontend` to remove or properly type
  the `test` configuration so `npm run build` succeeds locally.
- Run the Maven workflows on an environment with Maven installed (or rely on
  GitHub Actions CI) to confirm the `-Dmaven.multiModuleProjectDirectory=.` and
  GitHub Packages publishing changes.

### 2026-03-14 — `shopping-cart-payment` tests still reference legacy API

- After round 4 fixes (GitHub Packages repo, Maven settings, missing testcontainers
  dependency, stub exceptions) the payment service now compiles but the CI run
  fails in `RefundServiceIntegrationTest`. The tests still call the old
  `refundService.processRefund(paymentId, amount, reason, null)` signature and
  expect a `getRefundsByPaymentId` helper that no longer exists. The production
  method requires `(paymentId, amount, reason, userId, correlationId)`, so the
  test suite must be updated before CI can pass.

### 2026-03-14 — `shopping-cart-basket` golangci-lint rollout blocked

- Branch `feature/p4-linter` (PR #1) adds golangci-lint per the P4 linter plan.
  All GitHub Actions runs currently fail because golangci-lint reports existing
  issues in `cmd/server/main.go` (`logger.Sync()` return value ignored) and
  formatting drift in `cmd/server/main.go` plus `internal/model/cart.go`.
- Per the plan, no Go source changes were made. Decide whether to fix the
  reported issues or relax the lint configuration before merging the PR.
