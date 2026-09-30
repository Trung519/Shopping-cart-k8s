# System Patterns: rabbitmq-client-java

## Overall Architecture

The library is a Spring Boot auto-configuration library. Consumers add the `rabbitmq-client` JAR as a Maven dependency. Spring Boot's auto-configuration mechanism (via `AutoConfiguration.imports`) wires all beans at startup.

```
Spring Boot Application
    -> RabbitMQClientAutoConfiguration
        -> RabbitMQProperties (@ConfigurationProperties)
        -> VaultCredentialManager (conditional: vault.enabled=true)
        -> ConnectionManager (uses VaultCredentialManager or static creds)
        -> RabbitMQMetrics (conditional: MeterRegistry present)
        -> RetryConfig (Resilience4j RetryRegistry)
        -> CircuitBreakerConfig (Resilience4j CircuitBreakerRegistry)
        -> Publisher (RabbitTemplate-based)
        -> Consumer (SimpleMessageListenerContainer-based)
        -> DLQManager
        -> RabbitMQHealthIndicator (conditional: Actuator on classpath)
        -> VaultHealthIndicator (conditional: Vault enabled + Actuator)
```

## Design Patterns

### 1. Spring Boot Auto-Configuration

`RabbitMQClientAutoConfiguration` is annotated `@AutoConfiguration` and registered in `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`. Every `@Bean` method uses `@ConditionalOnMissingBean` so consuming applications can override any component by declaring their own bean of the same type.

Two `ConnectionManager` beans exist with different conditions:
- `connectionManagerWithVault`: requires `VaultCredentialManager` bean present
- `connectionManagerWithoutVault`: activated when `rabbitmq.vault.enabled=false`

This clean conditional split means the library works identically with or without Vault.

### 2. Nested Configuration Properties

`RabbitMQProperties` is a single `@ConfigurationProperties(prefix = "rabbitmq")` class with four static inner `@Data` classes: `Pool`, `Retry`, `CircuitBreaker`, `Vault`. All fields have defaults matching the other language implementations. `@Validated` + Jakarta annotations enforce constraints at context startup rather than at first use.

### 3. Spring Cloud Vault Integration

`VaultCredentialManager` uses Spring's `VaultTemplate` injected by Spring Cloud Vault auto-configuration. It reads credentials from `<backend>/creds/<role>` path and exposes them to `ConnectionManager`. Spring Cloud Vault handles Vault authentication (token, Kubernetes SA, etc.) transparently. `@Scheduled` or the renewal interval property drives credential refresh.

`VaultCredentials` is an immutable value object (record or `@Value`) holding `username`, `password`, `leaseId`, `leaseDuration`.

### 4. RabbitTemplate-Based Publisher

`Publisher` creates a `RabbitTemplate` from `ConnectionManager.getConnectionFactory()`. Configuration at construction time:
- `setMandatory(true)` — enables returns for unroutable messages
- `setReturnsCallback()` — logs returned messages
- Confirm mode via `rabbitTemplate.invoke(operations -> { ...; operations.waitForConfirms(timeout); })`

Body serialization order: `byte[]` passthrough -> `String` UTF-8 encode -> `ObjectMapper.writeValueAsBytes()` (JSON).

Message properties built from `PublishOptions`: `contentType`, `deliveryMode`, `messageId` (UUID), `timestamp`, `priority`, `expiration`, `correlationId`, `replyTo`, custom headers.

### 5. SimpleMessageListenerContainer Consumer

`Consumer` manages a `Map<String, SimpleMessageListenerContainer>` (keyed by consumer ID). Each call to `consume()`:
1. Declares the queue via `rabbitTemplate.execute(channel -> channel.queueDeclare(...))`
2. Creates a new `SimpleMessageListenerContainer` with `ChannelAwareMessageListener`
3. Sets `AcknowledgeMode.MANUAL` or `AUTO` from `ConsumeOptions`
4. Sets prefetch count
5. Calls `container.start()` and stores it in the map

On success: `channel.basicAck(deliveryTag, false)`.
On exception: `channel.basicNack(deliveryTag, false, requeueOnFailure)`.

`stop(consumerId)` stops and destroys the container. `stopAll()` iterates the map.

### 6. Resilience4j Integration

`RetryConfig` and `CircuitBreakerConfig` create Resilience4j `RetryRegistry` and `CircuitBreakerRegistry` beans populated from `RabbitMQProperties.Retry` and `RabbitMQProperties.CircuitBreaker` respectively. The `Publisher` and `Consumer` can use these registries to decorate their operations with `retry.executeCallable()` or `circuitBreaker.executeCallable()`.

Circuit breaker uses a sliding window (`SLIDING_WINDOW_TYPE.COUNT_BASED`) with configurable size and failure rate threshold (percentage-based, unlike the Go/Python threshold-count approach).

### 7. Micrometer Metrics

`RabbitMQMetrics` receives a `MeterRegistry` at construction. It creates `Counter`, `Timer`, and `Gauge` instruments lazily on first use. `trackPublish(exchange, routingKey, size)` returns a `Runnable` that records elapsed time and size on completion (same deferred-function pattern used in Go/Python siblings). `recordPublishError()` / `recordConsumeError()` increment dedicated error counters.

If no `MeterRegistry` is present on the classpath, a `SimpleMeterRegistry` is used as a no-op fallback (beans remain functional).

### 8. Health Indicators

`RabbitMQHealthIndicator` extends `AbstractHealthIndicator` and checks `ConnectionManager` connection status. `VaultHealthIndicator` checks Vault availability via `VaultCredentialManager`.

Both are registered only when Spring Actuator's `HealthIndicator` interface is on the classpath (`@ConditionalOnClass`).

Health state maps: UP = connected and credentials valid, DOWN = connection/credential failure.

### 9. DLQ Infrastructure

`DLQManager` is injected with `ConnectionManager` and `Publisher`. It uses `rabbitTemplate.execute()` to:
- Declare DLX (dead letter exchange, `direct` type)
- Declare DLQ
- Bind DLQ to DLX
- Declare source queue with `x-dead-letter-exchange` arg

`DLQConfig` is a record with source queue name, DLQ/DLX names, max retries, retry delay.
`DLQMessage` wraps an `org.springframework.amqp.core.Message` and exposes original exchange/routing-key, error info, and retry count extracted from headers.

### 10. Exception Hierarchy

```
RuntimeException
└── RabbitMQException (base class)
    ├── ConnectionException
    ├── PublishException
    ├── ConsumeException
    └── CircuitBreakerOpenException
```

All exceptions carry exchange/queue/routing-key context and a cause. Spring exception translation is not used; exceptions propagate as-is from the library to callers.

## Key Abstractions

| Abstraction | Package | Responsibility |
|---|---|---|
| `RabbitMQProperties` | config | Typed configuration with nested sections |
| `ConnectionManager` | connection | ConnectionFactory lifecycle; Vault or static creds |
| `VaultCredentialManager` | vault | Vault API: fetch, refresh, credentials object |
| `VaultCredentials` | vault | Immutable credential value object |
| `Publisher` | publisher | RabbitTemplate wrapper; confirm mode; JSON serialize |
| `PublishOptions` | publisher | Builder: exchange, routingKey, headers, confirm timeout |
| `BatchPublisher` | publisher | Accumulate + flush with confirms |
| `Consumer` | consumer | Container lifecycle map; start/stop consumers |
| `ConsumeOptions` | consumer | Builder: queue, autoAck, prefetch, QueueOptions |
| `MessageHandler` | consumer | `@FunctionalInterface` for message callbacks |
| `RetryConfig` | retry | Resilience4j RetryRegistry from properties |
| `CircuitBreakerConfig` | circuitbreaker | Resilience4j CircuitBreakerRegistry |
| `RabbitMQMetrics` | metrics | MeterRegistry-based counters, timers, gauges |
| `RabbitMQHealthIndicator` | health | Spring Actuator health for RabbitMQ connection |
| `VaultHealthIndicator` | health | Spring Actuator health for Vault |
| `DLQManager` | dlq | Infrastructure: DLX + DLQ declare/bind |
| `DLQConfig` | dlq | DLQ configuration record |
| `DLQMessage` | dlq | Dead letter message envelope |
| `RabbitMQClientAutoConfiguration` | (root) | Bean wiring with conditionals |
