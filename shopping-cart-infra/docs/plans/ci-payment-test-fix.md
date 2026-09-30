# Task Spec: shopping-cart-payment — CI Test Compile Fix (Round 4)

**Repo:** `wilddog64/shopping-cart-payment`
**Branch:** `fix/ci-stabilization` (push to existing branch)
**PR:** #1 (already open — push additional commits)
**Agent:** Codex

---

## Context

Dependency resolution is now fixed. The build fails at test compilation due to
pre-existing broken test code. This spec covers fixing the compile errors only.

**Do NOT touch** anything outside the files listed below.
**Do NOT update memory-bank until PR CI is green.**
**Do NOT fabricate commit SHAs.**

---

## Failures

```
BaseIntegrationTest.java:[8,40] package org.testcontainers.junit.jupiter does not exist
BaseIntegrationTest.java:[9,40] package org.testcontainers.junit.jupiter does not exist
BaseIntegrationTest.java:[18,2] cannot find symbol — class Testcontainers
PaymentControllerIntegrationTest.java:[4,36] cannot find symbol
PaymentControllerIntegrationTest.java:[406,13] cannot find symbol
RefundServiceIntegrationTest.java:[7,42] package com.shoppingcart.payment.exception does not exist
RefundServiceIntegrationTest.java:[8,42] package com.shoppingcart.payment.exception does not exist
```

---

## Fix 1 — Add missing testcontainers dependency

**File:** `pom.xml`

The `org.testcontainers.junit.jupiter` package comes from the `testcontainers-junit-jupiter`
artifact. Spring Boot 3.2.0 BOM manages the version via `testcontainers-bom`.

Add inside `<dependencies>`, in the test dependencies section:
```xml
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
```

No `<version>` needed — managed by Spring Boot BOM via testcontainers-bom.

---

## Fix 2 — Resolve missing exception package

**Files to inspect first:**
- `src/test/java/com/shoppingcart/payment/integration/RefundServiceIntegrationTest.java` lines 7-8
- `src/main/java/com/shoppingcart/payment/` — check if `exception` package exists

**If the `exception` package exists in main but imports are wrong:** fix the import paths.

**If the `exception` package does not exist:** check what exception classes are imported
and either:
- Create the missing classes with minimal stubs (empty class body, correct package)
- Or update the imports to use the correct existing exception class

Only add the minimum code needed to make the test compile. Do not implement business logic.

---

## Completion Criteria

- `Build and Test` CI job green ✅
- No changes to any file outside `pom.xml` and the identified test/source files
- Update memory-bank in `wilddog64/shopping-cart-payment` ONLY after CI is green
