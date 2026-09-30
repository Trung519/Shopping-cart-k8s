## CI Status (as of 2026-03-13)

**Branch:** `fix/ci-stabilization` — PR #1 open

| Job | Status |
|---|---|
| Build and Test | ✅ pass |
| Publish to GitHub Packages | ✅ pass |

**Package `com.shoppingcart:rabbitmq-client:1.0.0-SNAPSHOT` is published to GitHub Packages.**
PR #1 ready to merge.

Fix applied: added `publish` job to `java-ci.yml` — runs on `fix/ci-stabilization` and `main`
pushes. Needs only `build` (not `integration-test`) to proceed.

---# Active Context: rabbitmq-client-java

## Current State

The project is **In Development**. The core library (`rabbitmq-client` module) is fully implemented. The demo path (`make demo`) works end-to-end. A known issue affects the CLI tools. Test coverage exists for configuration and options classes but not for the main runtime components.

## What Is Currently Implemented

### Core Library (`rabbitmq-client/src/main/java/com/shoppingcart/rabbitmq/`)
- `RabbitMQClientAutoConfiguration` — full auto-configuration with all conditional beans
- `config/RabbitMQProperties` — `@ConfigurationProperties` with nested Pool, Retry, CircuitBreaker, Vault inner classes; `@Validated` with Jakarta constraints
- `connection/ConnectionManager` — AMQP `ConnectionFactory` lifecycle, Vault and static credential paths
- `vault/VaultCredentialManager` — Spring Cloud Vault `VaultTemplate`-based credential fetch and renewal
- `vault/VaultCredentials` — credential value object
- `publisher/Publisher` — `RabbitTemplate`-based publishing with confirm mode and returns callback
- `publisher/PublishOptions` — builder pattern with exchange, routing key, delivery mode, headers, priority, expiration, correlation ID, confirm timeout
- `publisher/BatchPublisher` — batch accumulation and flush with confirms
- `consumer/Consumer` — `SimpleMessageListenerContainer` lifecycle map, manual/auto-ack, `stop()`/`stopAll()`
- `consumer/ConsumeOptions` — builder: queue, autoAck, prefetchCount, requeueOnFailure, QueueOptions nested class
- `consumer/MessageHandler` — `@FunctionalInterface`
- `retry/RetryConfig` — Resilience4j `RetryRegistry` from properties
- `circuitbreaker/CircuitBreakerConfig` — Resilience4j `CircuitBreakerRegistry` from properties
- `metrics/RabbitMQMetrics` — `MeterRegistry` wrapper, deferred tracking functions
- `health/RabbitMQHealthIndicator` — Spring Actuator `HealthIndicator`
- `health/VaultHealthIndicator` — Spring Actuator `HealthIndicator`
- `dlq/DLQManager`, `dlq/DLQConfig`, `dlq/DLQMessage` — DLQ infrastructure
- `exception/` — `RabbitMQException`, `ConnectionException`, `PublishException`, `ConsumeException`, `CircuitBreakerOpenException`

### CLI Module (`rabbitmq-cli/`)
- `cli/PublisherCli` — Spring Boot `CommandLineRunner` for publishing
- `cli/ConsumerCli` — Spring Boot `CommandLineRunner` for consuming
- `application.yml` — CLI application configuration

### Examples Module (`rabbitmq-examples/`)
- `examples/DemoExample` — combined publisher + consumer demo (`make demo`)
- `examples/PublisherExample` — standalone publisher
- `examples/ConsumerExample` — standalone consumer
- `application.yml` + `application-demo.yml` — example configuration with demo profile

### Build & CI
- `Makefile` — comprehensive targets: build, test, coverage, demo, CLI, dev environment, code quality
- `.github/workflows/java-ci.yml` — GitHub Actions CI pipeline
- `Jenkinsfile` — Jenkins pipeline
- `bin/` — `build.sh`, `run-cli.sh`, `run-examples.sh`, `run-tests.sh`, `cli-demo.sh`, `setup-dev.sh`

### Tests
- `RabbitMQPropertiesTest` — config loading and validation
- `PublishOptionsTest` — builder defaults and full options
- `ConsumeOptionsTest` — builder defaults
- `VaultCredentialsTest` — credential value object
- `CircuitBreakerConfigTest` — Resilience4j config construction
- `RetryConfigTest` — retry config construction
- `RabbitMQMetricsTest` — metrics wiring
- `DLQConfigTest`, `DLQMessageTest` — DLQ data objects
- `ExceptionTest` — exception hierarchy and messages

### Documentation
- `README.md` — full feature list, quick start, configuration table, module overview
- `CLAUDE.md` — AI coding guidance including known issues
- `docs/guides/testing.md` — comprehensive testing guide with examples
- `docs/guides/ci-cd.md` — CI/CD pipeline documentation
- `docs/guides/README.md`

## Known Issues

### CLI Tools — Both CommandLineRunner Beans Fire
When `rabbitmq-cli` is built as a single JAR containing both `PublisherCli` and `ConsumerCli` (both `CommandLineRunner` implementations), Spring Boot's application runner infrastructure invokes both with the same command-line args. The consumer will start with publish args; the publisher will start with consumer args.

**Workaround**: Use `make demo` (DemoExample) which correctly orchestrates publisher and consumer in one Spring Boot application without the `CommandLineRunner` conflict.

**Future Fix**: Separate the CLI into two distinct Spring Boot main classes each in their own executable JAR, or use Spring Shell, or use `@ConditionalOnProperty` to activate only one at a time.

## Active Development Areas

- Expanding test coverage to cover `Publisher`, `Consumer`, `ConnectionManager`, `VaultCredentialManager` (currently none of these have test files)
- Resolving the CLI tools `CommandLineRunner` conflict
- Verifying integration tests work with Testcontainers (infrastructure is wired but may not have been run end-to-end)
