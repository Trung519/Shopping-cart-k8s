# Project Brief: rabbitmq-client-java

## What the Project Does

`rabbitmq-client-java` is a production-ready Java client library for RabbitMQ built on Spring Boot 3.2 and Java 21. It provides a Spring-native way to connect to RabbitMQ with HashiCorp Vault dynamic credential management, Resilience4j circuit breakers, exponential-backoff retry, Micrometer/Prometheus metrics, Spring Actuator health indicators, and dead letter queue support.

The library ships as a Spring Boot auto-configuration JAR that consuming Spring Boot applications can add as a Maven dependency. All components are conditionally enabled and overridable. It is part of a multi-language RabbitMQ client family (alongside Go and Python siblings) built for the shopping-cart microservices platform.

## Goals

1. Provide a Spring Boot-native RabbitMQ client that auto-configures all components on startup
2. Eliminate hardcoded credentials by defaulting to Vault-backed dynamic credential management
3. Integrate cleanly with the Spring ecosystem: Spring Actuator health, Micrometer metrics, Spring Cloud Vault, `@ConfigurationProperties`
4. Provide fault tolerance via Resilience4j circuit breakers and retry
5. Ship CLI tools and example applications for demos and operational use
6. Achieve feature parity with Go and Python sibling implementations

## Scope

### In Scope
- Spring Boot auto-configuration (`RabbitMQClientAutoConfiguration`)
- `@ConfigurationProperties` configuration class with nested `Pool`, `Retry`, `CircuitBreaker`, `Vault` sections
- `ConnectionManager` supporting both Vault-backed and static credentials
- `VaultCredentialManager` using Spring Cloud Vault's `VaultTemplate`
- `Publisher` with publisher confirms, JSON serialization, returns callback
- `BatchPublisher` for high-throughput batch publishing
- `Consumer` based on `SimpleMessageListenerContainer` with manual/auto-ack
- `MessageHandler` functional interface for message callbacks
- Resilience4j `RetryConfig` and `CircuitBreakerConfig` wired from properties
- `RabbitMQMetrics` wrapping `MeterRegistry` for Micrometer metrics
- `RabbitMQHealthIndicator` and `VaultHealthIndicator` for Spring Actuator
- `DLQManager` for dead letter queue infrastructure
- `DLQMessage` / `DLQConfig` for DLQ operations
- Full exception hierarchy rooted at `RabbitMQException`
- CLI tools module (`rabbitmq-cli`) for operational use
- Examples module (`rabbitmq-examples`) with `DemoExample`, `PublisherExample`, `ConsumerExample`
- Makefile with comprehensive targets
- Unit tests, JaCoCo coverage reporting
- GitHub Actions CI and Jenkinsfile

### Out of Scope
- Go and Python implementations (separate repositories)
- RabbitMQ cluster provisioning
- Vault cluster provisioning
- Application business logic

## Related Repositories

- `rabbitmq-client-go` — Go sibling
- `rabbitmq-client-python` — Python sibling (original reference implementation)
- `shopping-cart-infra` — Kubernetes manifests, RabbitMQ cluster, Vault configuration
- `observability-stack` — Prometheus + Grafana deployment

## Current Status

**In Development.** Core library is fully implemented. `make demo` works end-to-end. CLI tools have a known issue (both `CommandLineRunner` beans run with same args when in same JAR). Unit tests cover config, options, and exception classes. Integration tests are wired for Testcontainers but may need further work.
