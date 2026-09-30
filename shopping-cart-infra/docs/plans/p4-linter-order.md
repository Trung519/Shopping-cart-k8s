# Spec: P4 Linter — shopping-cart-order (Checkstyle + OWASP)

**Date:** 2026-03-14
**Repo:** `wilddog64/shopping-cart-order`
**Branch:** create `feature/p4-linter` from main
**Assigned to:** Codex
**Working directory:** `/Users/cliang/src/gitrepo/personal/shopping-carts/shopping-cart-order`

---

## Background

Order is a Java 21 / Spring Boot service built with Maven. Add Checkstyle (code style) and
OWASP Dependency Check (CVE scanning) to the Maven build and CI.

---

## Changes Required

### 1. Add Checkstyle config file `checkstyle.xml` at repo root

```xml
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
    "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
    "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
  <property name="severity" value="error"/>
  <module name="TreeWalker">
    <module name="CyclomaticComplexity">
      <property name="max" value="10"/>
    </module>
    <module name="MethodLength">
      <property name="max" value="80"/>
    </module>
    <module name="ParameterNumber">
      <property name="max" value="7"/>
    </module>
    <module name="NestedIfDepth">
      <property name="max" value="3"/>
    </module>
  </module>
</module>
```

### 2. Add plugins to `pom.xml` inside `<build><plugins>`

```xml
<!-- Checkstyle -->
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-checkstyle-plugin</artifactId>
  <version>3.3.1</version>
  <configuration>
    <configLocation>checkstyle.xml</configLocation>
    <failsOnError>true</failsOnError>
    <consoleOutput>true</consoleOutput>
  </configuration>
  <executions>
    <execution>
      <id>checkstyle</id>
      <phase>validate</phase>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>

<!-- OWASP Dependency Check -->
<plugin>
  <groupId>org.owasp</groupId>
  <artifactId>dependency-check-maven</artifactId>
  <version>9.0.9</version>
  <configuration>
    <failBuildOnCVSS>9</failBuildOnCVSS>
    <skipTestScope>true</skipTestScope>
    <nvdApiDelay>4000</nvdApiDelay>
  </configuration>
  <executions>
    <execution>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>
```

### 3. Add lint job to `.github/workflows/ci.yml`

Add a `lint` job before `build`:

```yaml
  lint:
    name: Checkstyle
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: read
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: 21
          cache: maven

      - name: Run Checkstyle
        run: mvn -B checkstyle:check -s .github/maven-settings.xml
        env:
          PACKAGES_TOKEN: ${{ secrets.PACKAGES_TOKEN }}
```

Add `needs: [lint]` to the `build` job.

**Note:** OWASP runs as part of `mvn verify` in the build job — no separate CI step needed.
OWASP only fails the build on CVSS ≥ 9 (critical CVEs).

---

## Rules

- Do NOT fix source code to pass Checkstyle — report violations and stop
- Do NOT change `failBuildOnCVSS` below 9 — critical CVEs only
- Do NOT change the `publish` job
- First command: `hostname && uname -n`

---

## Completion Steps

1. Create branch `feature/p4-linter` from main
2. Add `checkstyle.xml`, update `pom.xml`, update `.github/workflows/ci.yml`
3. Push to `feature/p4-linter` on `wilddog64/shopping-cart-order`
4. Open PR against main
5. Wait for CI: `gh run list --repo wilddog64/shopping-cart-order --branch feature/p4-linter`
6. If Checkstyle fails: report violations and stop — do NOT fix source code
7. Verify SHA: `gh api repos/wilddog64/shopping-cart-order/git/commits/<sha>`
8. Update `wilddog64/shopping-cart-order/memory-bank/activeContext.md`
9. Do NOT update memory-bank until CI green (or violations documented)

---

## Completion Report Template

```
Repo: wilddog64/shopping-cart-order
Branch: feature/p4-linter
PR URL: <url>
Commit SHA (verified): <sha>
CI run ID: <run_id>
CI conclusion: success / failure
Checkstyle result: PASS / FAIL (list violations if any)
OWASP result: PASS / FAIL
Files changed:
  - checkstyle.xml — created
  - pom.xml — checkstyle + owasp plugins added
  - .github/workflows/ci.yml — lint job added, build needs lint
```
