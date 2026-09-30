# Progress: rabbitmq-client-java

## What Is Built

### Core Library (`rabbitmq-client`)
- [x] `RabbitMQClientAutoConfiguration` — auto-configuration entry point with conditional beans
- [x] `RabbitMQProperties` — full `@ConfigurationProperties` with nested Pool/Retry/CircuitBreaker/Vault
- [x] `ConnectionManager` — dual-path: Vault credentials or static credentials
- [x] `VaultCredentialManager` — Spring Cloud Vault `VaultTemplate` integration, renewal
- [x] `VaultCredentials` — credential value object
- [x] `Publisher` — `RabbitTemplate` wrapper, confirm mode, returns callback, JSON serialize
- [x] `PublishOptions` — builder with all AMQP message properties
- [x] `BatchPublisher` — batch accumulate and flush
- [x] `Consumer` — `SimpleMessageListenerContainer` map, manual/auto-ack, prefetch
- [x] `ConsumeOptions` — builder with QueueOptions nested class
- [x] `MessageHandler` — `@FunctionalInterface`
- [x] `RetryConfig` — Resilience4j `RetryRegistry` from properties
- [x] `CircuitBreakerConfig` — Resilience4j `CircuitBreakerRegistry` from properties
- [x] `RabbitMQMetrics` — `MeterRegistry` wrapper
- [x] `RabbitMQHealthIndicator` — Spring Actuator health for RabbitMQ
- [x] `VaultHealthIndicator` — Spring Actuator health for Vault
- [x] `DLQManager`, `DLQConfig`, `DLQMessage`
- [x] Full exception hierarchy: `RabbitMQException` -> `ConnectionException`, `PublishException`, `ConsumeException`, `CircuitBreakerOpenException`
- [x] `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports` — auto-config registration

### CLI Module (`rabbitmq-cli`)
- [x] `PublisherCli` — `CommandLineRunner` publisher
- [x] `ConsumerCli` — `CommandLineRunner` consumer
- [x] `application.yml` — CLI configuration

### Examples Module (`rabbitmq-examples`)
- [x] `DemoExample` — combined publisher + consumer (`make demo`)
- [x] `PublisherExample` — standalone publisher
- [x] `ConsumerExample` — standalone consumer (blocks indefinitely)
- [x] `application.yml` + `application-demo.yml` — demo profile (port 30672, demo/demo, no Vault)

### Build & CI
- [x] Parent `pom.xml` with Spring Boot BOM, Spring Cloud BOM, Resilience4j BOM, Testcontainers BOM
- [x] Child POMs for all three modules
- [x] `Makefile` — build, test, coverage, demo, CLI, dev environment, quality targets
- [x] `.github/workflows/java-ci.yml` — GitHub Actions
- [x] `Jenkinsfile` — Jenkins pipeline
- [x] `bin/` scripts — build, run-cli, run-examples, run-tests, cli-demo, setup-dev

### Tests (Unit)
- [x] `RabbitMQPropertiesTest`
- [x] `PublishOptionsTest`
- [x] `ConsumeOptionsTest`
- [x] `VaultCredentialsTest`
- [x] `CircuitBreakerConfigTest`
- [x] `RetryConfigTest`
- [x] `RabbitMQMetricsTest`
- [x] `DLQConfigTest`
- [x] `DLQMessageTest`
- [x] `ExceptionTest`

### Documentation
- [x] `README.md` — features, quick start, configuration, module table, health endpoints
- [x] `CLAUDE.md` — comprehensive AI guidance including known issues and workarounds
- [x] `docs/guides/testing.md` — unit and integration test guide with code examples
- [x] `docs/guides/ci-cd.md`
- [x] `docs/guides/README.md`

## What Is Pending

### Test Coverage (Priority)
- [ ] `PublisherTest` — unit tests with Mockito-mocked `RabbitTemplate`
- [ ] `ConsumerTest` — unit tests for container lifecycle, ack/nack behavior
- [ ] `ConnectionManagerTest` — unit tests for factory creation, credential wiring
- [ ] `VaultCredentialManagerTest` — unit tests with mocked `VaultTemplate`
- [ ] Integration tests with Testcontainers (infra is wired in test scope; need test classes)
- [ ] End-to-end integration test: publish -> consume roundtrip with real RabbitMQ container

### Known Issues to Fix
- [ ] **CLI CommandLineRunner conflict**: Both `PublisherCli` and `ConsumerCli` run when in same JAR
  - Options: separate JARs, Spring Shell, `@ConditionalOnProperty`, Spring Profiles

### Operational
- [ ] Verify `make dev-setup` Vault configuration works end-to-end with the CLI
- [ ] Docker Compose file for dev environment (referenced in `dev-start`/`dev-stop` targets but file not found in tree)

## Coverage Targets

JaCoCo configuration (from `docs/guides/testing.md`) targets:
- Line coverage: **80%** minimum
- Branch coverage: **70%** minimum

Current state: Only configuration/options/exception classes are tested. Core runtime classes (Publisher, Consumer, ConnectionManager, VaultCredentialManager) have no tests yet — estimated current coverage well below 80%.

## Demo Verification

The following path is confirmed working:
```bash
make demo
# Builds -> installs -> runs DemoExample with demo profile
# Connects to RabbitMQ on localhost:30672 with demo/demo
# Publishes 8 test messages -> consumer receives and prints them -> clean shutdown
```
