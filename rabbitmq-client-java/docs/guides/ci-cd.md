# CI/CD Guide

This guide covers the continuous integration and deployment setup for the RabbitMQ client library.

## Table of Contents

- [Overview](#overview)
- [GitHub Actions](#github-actions)
- [Jenkins Pipeline](#jenkins-pipeline)
- [Build Process](#build-process)
- [Release Process](#release-process)
- [Artifact Publishing](#artifact-publishing)

---

## Overview

The project uses two CI/CD systems:

| System | Purpose | Trigger |
|--------|---------|---------|
| GitHub Actions | PR validation, main branch builds | Push, PR |
| Jenkins | Production releases, artifact publishing | Manual, tags |

---

## GitHub Actions

### Workflow File

Located at: `.github/workflows/java-ci.yml`

### Pipeline Stages

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Build     │───▶│    Test     │───▶│  Coverage   │───▶│  Analyze    │
│             │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Workflow Configuration

```yaml
name: Java CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest

    services:
      rabbitmq:
        image: rabbitmq:3.12-management-alpine
        ports:
          - 5672:5672
          - 15672:15672
        options: >-
          --health-cmd "rabbitmqctl status"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
          cache: maven

      - name: Build
        run: mvn -B compile

      - name: Test
        run: mvn -B test

      - name: Integration Tests
        run: mvn -B verify -P integration-tests

      - name: Coverage Report
        run: mvn -B jacoco:report

      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: target/site/jacoco/jacoco.xml

      - name: Package
        run: mvn -B package -DskipTests

      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: jars
          path: |
            rabbitmq-client/target/*.jar
            rabbitmq-cli/target/*.jar
```

### Branch Protection

Recommended settings for `main` branch:

- Require status checks to pass
- Require branches to be up to date
- Required checks: `build`
- Require pull request reviews

---

## Jenkins Pipeline

### Jenkinsfile

Located at: `Jenkinsfile`

### Pipeline Structure

```groovy
pipeline {
    agent any

    tools {
        maven 'Maven-3.9'
        jdk 'JDK-21'
    }

    environment {
        MAVEN_OPTS = '-Xmx1024m'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'mvn -B clean compile'
            }
        }

        stage('Test') {
            steps {
                sh 'mvn -B test'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                }
            }
        }

        stage('Integration Tests') {
            when {
                anyOf {
                    branch 'main'
                    buildingTag()
                }
            }
            steps {
                sh 'mvn -B verify -P integration-tests'
            }
        }

        stage('Coverage') {
            steps {
                sh 'mvn -B jacoco:report'
                jacoco(
                    execPattern: '**/target/*.exec',
                    classPattern: '**/target/classes',
                    sourcePattern: '**/src/main/java'
                )
            }
        }

        stage('Package') {
            steps {
                sh 'mvn -B package -DskipTests'
            }
        }

        stage('Deploy to Nexus') {
            when {
                anyOf {
                    branch 'main'
                    buildingTag()
                }
            }
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'nexus-credentials',
                        usernameVariable: 'NEXUS_USER',
                        passwordVariable: 'NEXUS_PASS'
                    )
                ]) {
                    sh 'mvn -B deploy -DskipTests'
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: '**/target/*.jar', fingerprint: true
            cleanWs()
        }
        failure {
            emailext(
                subject: "Build Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: "Check console output at ${env.BUILD_URL}",
                recipientProviders: [developers()]
            )
        }
    }
}
```

### Jenkins Requirements

- Java 21 tool configured
- Maven 3.9+ tool configured
- Docker available on agent (for integration tests)
- Nexus credentials configured

---

## Build Process

### Maven Profiles

```xml
<profiles>
    <!-- Unit tests only (default) -->
    <profile>
        <id>unit-tests</id>
        <activation>
            <activeByDefault>true</activeByDefault>
        </activation>
    </profile>

    <!-- Integration tests -->
    <profile>
        <id>integration-tests</id>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-failsafe-plugin</artifactId>
                    <executions>
                        <execution>
                            <goals>
                                <goal>integration-test</goal>
                                <goal>verify</goal>
                            </goals>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>

    <!-- Release profile -->
    <profile>
        <id>release</id>
        <build>
            <plugins>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-source-plugin</artifactId>
                    <executions>
                        <execution>
                            <id>attach-sources</id>
                            <goals>
                                <goal>jar-no-fork</goal>
                            </goals>
                        </execution>
                    </executions>
                </plugin>
                <plugin>
                    <groupId>org.apache.maven.plugins</groupId>
                    <artifactId>maven-javadoc-plugin</artifactId>
                    <executions>
                        <execution>
                            <id>attach-javadocs</id>
                            <goals>
                                <goal>jar</goal>
                            </goals>
                        </execution>
                    </executions>
                </plugin>
            </plugins>
        </build>
    </profile>
</profiles>
```

### Build Commands

```bash
# Development build
mvn clean compile

# Run tests
mvn test

# Package without tests
mvn package -DskipTests

# Full build with integration tests
mvn verify -P integration-tests

# Release build
mvn clean deploy -P release
```

---

## Release Process

### Versioning

Follow semantic versioning: `MAJOR.MINOR.PATCH`

- `MAJOR`: Breaking changes
- `MINOR`: New features, backwards compatible
- `PATCH`: Bug fixes

### Creating a Release

```bash
# 1. Update version
mvn versions:set -DnewVersion=1.0.0

# 2. Commit version change
git add pom.xml */pom.xml
git commit -m "Release 1.0.0"

# 3. Create tag
git tag -a v1.0.0 -m "Release 1.0.0"

# 4. Push
git push origin main --tags

# 5. Set next development version
mvn versions:set -DnewVersion=1.0.1-SNAPSHOT
git add pom.xml */pom.xml
git commit -m "Prepare for next development iteration"
git push origin main
```

### Automated Release

Using Maven Release Plugin:

```bash
# Prepare release (updates versions, creates tag)
mvn release:prepare -DautoVersionSubmodules=true

# Perform release (builds and deploys)
mvn release:perform

# Cleanup if something goes wrong
mvn release:rollback
```

---

## Artifact Publishing

### Repository Configuration

```xml
<distributionManagement>
    <repository>
        <id>releases</id>
        <url>https://nexus.example.com/repository/maven-releases/</url>
    </repository>
    <snapshotRepository>
        <id>snapshots</id>
        <url>https://nexus.example.com/repository/maven-snapshots/</url>
    </snapshotRepository>
</distributionManagement>
```

### Maven Settings

`~/.m2/settings.xml`:

```xml
<settings>
    <servers>
        <server>
            <id>releases</id>
            <username>${env.NEXUS_USER}</username>
            <password>${env.NEXUS_PASS}</password>
        </server>
        <server>
            <id>snapshots</id>
            <username>${env.NEXUS_USER}</username>
            <password>${env.NEXUS_PASS}</password>
        </server>
    </servers>
</settings>
```

### Published Artifacts

| Artifact | Description |
|----------|-------------|
| `rabbitmq-client-1.0.0.jar` | Core library |
| `rabbitmq-client-1.0.0-sources.jar` | Source code |
| `rabbitmq-client-1.0.0-javadoc.jar` | JavaDoc |
| `rabbitmq-cli-1.0.0.jar` | CLI tools |

---

## Environment Variables

### Required for CI

| Variable | Description |
|----------|-------------|
| `NEXUS_USER` | Nexus repository username |
| `NEXUS_PASS` | Nexus repository password |
| `CODECOV_TOKEN` | Codecov upload token |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `MAVEN_OPTS` | JVM options for Maven | `-Xmx1024m` |
| `JAVA_HOME` | Java installation path | Auto-detected |

---

## Troubleshooting

### Build Failures

**Out of memory**
```bash
export MAVEN_OPTS="-Xmx2048m"
mvn clean install
```

**Test failures in CI**
- Check Docker service is available
- Verify RabbitMQ container started
- Increase timeouts for slow CI environments

**Artifact upload fails**
- Verify Nexus credentials
- Check repository URL is correct
- Ensure version doesn't already exist (for releases)

### Useful Commands

```bash
# Skip tests
mvn install -DskipTests

# Debug mode
mvn -X clean test

# Specific module only
mvn install -pl rabbitmq-client -am

# Offline mode (use cached dependencies)
mvn -o clean install
```
