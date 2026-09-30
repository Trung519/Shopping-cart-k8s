# Spec: P4 Linter — shopping-cart-payment (Checkstyle + SpotBugs)

**Date:** 2026-03-14
**Repo:** `wilddog64/shopping-cart-payment`
**Branch:** create `feature/p4-linter` from main
**Assigned to:** Codex
**Working directory:** `/Users/cliang/src/gitrepo/personal/shopping-carts/shopping-cart-payment`

---

## Background

Payment is a Java 21 / Spring Boot service built with Maven. Add Checkstyle (code style)
and SpotBugs (static bug analysis) to the Maven build and CI.

---

## Changes Required

### 1. Add `checkstyle.xml` at repo root

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

<!-- SpotBugs -->
<plugin>
  <groupId>com.github.spotbugs</groupId>
  <artifactId>spotbugs-maven-plugin</artifactId>
  <version>4.8.3.1</version>
  <configuration>
    <effort>Max</effort>
    <threshold>High</threshold>
    <failOnError>true</failOnError>
  </configuration>
  <executions>
    <execution>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>
```

### 3. Add lint job to `.github/workflows/ci.yaml`

Add a `lint` job before `build`:

```yaml
  lint:
    name: Checkstyle & SpotBugs
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: read
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: 'temurin'
          cache: maven

      - name: Run Checkstyle
        run: ./mvnw -B checkstyle:check -s .github/maven-settings.xml
        env:
          PACKAGES_TOKEN: ${{ secrets.PACKAGES_TOKEN }}

      - name: Run SpotBugs
        run: ./mvnw -B spotbugs:check -DskipTests -s .github/maven-settings.xml
        env:
          PACKAGES_TOKEN: ${{ secrets.PACKAGES_TOKEN }}
```

Add `needs: [lint]` to the `build` job.

---

## Rules

- Do NOT fix source code to pass Checkstyle or SpotBugs — report violations and stop
- SpotBugs threshold is `High` — only high-severity bugs fail the build
- Do NOT change the existing `build` or `docker` jobs
- First command: `hostname && uname -n`

---

## Completion Steps

1. Create branch `feature/p4-linter` from main
2. Add `checkstyle.xml`, update `pom.xml`, update `.github/workflows/ci.yaml`
3. Push to `feature/p4-linter` on `wilddog64/shopping-cart-payment`
4. Open PR against main
5. Wait for CI: `gh run list --repo wilddog64/shopping-cart-payment --branch feature/p4-linter`
6. If Checkstyle or SpotBugs fails: report violations and stop — do NOT fix source code
7. Verify SHA: `gh api repos/wilddog64/shopping-cart-payment/git/commits/<sha>`
8. Update `wilddog64/shopping-cart-payment/memory-bank/activeContext.md`
9. Do NOT update memory-bank until CI green (or violations documented)

---

## Completion Report Template

```
Repo: wilddog64/shopping-cart-payment
Branch: feature/p4-linter
PR URL: <url>
Commit SHA (verified): <sha>
CI run ID: <run_id>
CI conclusion: success / failure
Checkstyle result: PASS / FAIL (list violations if any)
SpotBugs result: PASS / FAIL
Files changed:
  - checkstyle.xml — created
  - pom.xml — checkstyle + spotbugs plugins added
  - .github/workflows/ci.yaml — lint job added, build needs lint
```
