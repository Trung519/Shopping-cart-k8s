# RabbitMQ Client Library - API Guide

This guide covers the core components and their usage patterns.

## Table of Contents

- [Publisher](#publisher)
- [Consumer](#consumer)
- [Connection Manager](#connection-manager)
- [Vault Integration](#vault-integration)
- [Circuit Breaker](#circuit-breaker)
- [Retry Configuration](#retry-configuration)
- [Metrics](#metrics)
- [Health Checks](#health-checks)
- [Dead Letter Queue](#dead-letter-queue)

---

## Publisher

The `Publisher` component handles message publishing with support for confirmations, batching, and various delivery options.

### Basic Usage

```java
@Autowired
private Publisher publisher;

// Simple publish with exchange and routing key
publisher.publish("events", "order.created", Map.of(
    "orderId", "ORD-123",
    "amount", 99.99
));
```

### PublishOptions

Use `PublishOptions` for fine-grained control:

```java
PublishOptions options = PublishOptions.builder()
    .exchange("events")
    .routingKey("order.created")
    .mandatory(true)           // Return if unroutable
    .persistent(true)          // Survive broker restart
    .priority(5)               // Message priority (0-9)
    .expiration(Duration.ofMinutes(5))  // TTL
    .contentType("application/json")
    .header("x-trace-id", traceId)
    .build();

publisher.publish(options, orderData);
```

### Publisher Confirms

```java
// With confirmation (waits for broker ack)
boolean confirmed = publisher.publishWithConfirm(options, message, Duration.ofSeconds(5));
if (!confirmed) {
    log.warn("Message not confirmed by broker");
}
```

### Batch Publishing

```java
@Autowired
private BatchPublisher batchPublisher;

List<Message> messages = orders.stream()
    .map(order -> new Message("order.created", order))
    .toList();

batchPublisher.publishBatch("events", messages);
```

---

## Consumer

The `Consumer` component handles message consumption with support for manual/auto acknowledgment.

### Basic Usage

```java
@Autowired
private Consumer consumer;

ConsumeOptions options = ConsumeOptions.builder()
    .queue("order-events")
    .autoAck(false)           // Manual acknowledgment
    .prefetchCount(10)        // Messages per consumer
    .build();

consumer.consume(options, message -> {
    String body = new String(message.getBody());
    log.info("Received: {}", body);
    // Message auto-acked on successful return
});
```

### Manual Acknowledgment

```java
consumer.consume(options, (message, channel) -> {
    try {
        processOrder(message);
        channel.basicAck(message.getDeliveryTag(), false);
    } catch (Exception e) {
        // Requeue on failure
        channel.basicNack(message.getDeliveryTag(), false, true);
    }
});
```

### Queue Declaration

```java
// Declare queue with options
consumer.declareQueue("order-events", QueueOptions.builder()
    .durable(true)
    .exclusive(false)
    .autoDelete(false)
    .deadLetterExchange("dlx")
    .messageTtl(Duration.ofHours(24))
    .build());

// Bind to exchange
consumer.bindQueue("order-events", "events", "order.*");
```

### Stopping Consumers

```java
// Stop specific consumer
consumer.stop("consumer-tag");

// Stop all consumers
consumer.stopAll();
```

---

## Connection Manager

Manages RabbitMQ connections with Vault integration and pooling.

### Configuration

```yaml
rabbitmq:
  host: localhost
  port: 5672
  vhost: /
  pool:
    size: 10                    # Channel cache size
    heartbeat: 60s              # Connection heartbeat
    acquire-timeout: 10s        # Connection acquire timeout
```

### Programmatic Access

```java
@Autowired
private ConnectionManager connectionManager;

// Get connection factory
ConnectionFactory factory = connectionManager.getConnectionFactory();

// Check health
boolean healthy = connectionManager.isHealthy();

// Get statistics
ConnectionStats stats = connectionManager.getStats();
log.info("Active channels: {}, Idle: {}",
    stats.activeChannels(), stats.idleChannels());
```

---

## Vault Integration

Dynamic credential management with HashiCorp Vault.

### Configuration

```yaml
rabbitmq:
  vault:
    enabled: true
    role: rabbitmq-role        # Vault role name
    backend: rabbitmq          # Vault secrets engine path

spring:
  cloud:
    vault:
      uri: http://vault:8200
      authentication: KUBERNETES  # or TOKEN
      kubernetes:
        role: app-role
        service-account-token-file: /var/run/secrets/kubernetes.io/serviceaccount/token
```

### Credential Lifecycle

```java
@Autowired
private VaultCredentialManager vaultManager;

// Get current credentials
VaultCredentials creds = vaultManager.getCredentials();
log.info("Lease expires at: {}", creds.expiresAt());

// Force credential refresh
VaultCredentials newCreds = vaultManager.fetchCredentials();

// Revoke on shutdown (automatic with @PreDestroy)
vaultManager.revokeCredentials();
```

### Static Credentials (Vault Disabled)

```yaml
rabbitmq:
  vault:
    enabled: false
  username: guest
  password: guest
```

---

## Circuit Breaker

Resilience4j circuit breaker for fault tolerance.

### Configuration

```yaml
rabbitmq:
  circuit-breaker:
    enabled: true
    failure-rate-threshold: 50      # % failures to open
    wait-duration-in-open-state: 30s
    permitted-calls-in-half-open: 3
    sliding-window-size: 10
```

### Programmatic Access

```java
@Autowired
private CircuitBreakerConfig circuitBreakerConfig;

CircuitBreaker breaker = circuitBreakerConfig.getCircuitBreaker("publisher");

// Check state
CircuitBreaker.State state = breaker.getState();  // CLOSED, OPEN, HALF_OPEN

// Get metrics
CircuitBreaker.Metrics metrics = breaker.getMetrics();
float failureRate = metrics.getFailureRate();
```

### Event Handling

```java
breaker.getEventPublisher()
    .onStateTransition(event ->
        log.warn("Circuit breaker state changed: {} -> {}",
            event.getStateTransition().getFromState(),
            event.getStateTransition().getToState()));
```

---

## Retry Configuration

Exponential backoff retry with jitter.

### Configuration

```yaml
rabbitmq:
  retry:
    max-attempts: 3
    initial-interval: 1s
    max-interval: 30s
    multiplier: 2.0
    jitter: true
```

### Programmatic Usage

```java
@Autowired
private RetryConfig retryConfig;

RetryTemplate retryTemplate = retryConfig.createRetryTemplate();

retryTemplate.execute(context -> {
    publisher.publish("events", "order.created", message);
    return null;
});
```

---

## Metrics

Micrometer metrics for Prometheus/Grafana integration.

### Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `rabbitmq.messages.published` | Counter | Messages published |
| `rabbitmq.messages.consumed` | Counter | Messages consumed |
| `rabbitmq.publish.latency` | Timer | Publish latency |
| `rabbitmq.consume.latency` | Timer | Message processing time |
| `rabbitmq.connection.active` | Gauge | Active connections |
| `rabbitmq.channel.active` | Gauge | Active channels |
| `rabbitmq.circuit.state` | Gauge | Circuit breaker state |

### Custom Metrics

```java
@Autowired
private RabbitMQMetrics metrics;

// Record custom publish
Runnable complete = metrics.trackPublish("events", "order.created", bodySize);
try {
    publisher.publish(...);
    complete.run();  // Records success
} catch (Exception e) {
    metrics.recordError("publish", e);
}
```

### Prometheus Endpoint

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus
```

Access at: `http://localhost:8080/actuator/prometheus`

---

## Health Checks

Spring Boot Actuator health indicators.

### RabbitMQ Health

```java
@Component
public class RabbitMQHealthIndicator implements HealthIndicator {
    // Checks connection factory health
    // Returns UP, DOWN, or OUT_OF_SERVICE
}
```

Access at: `http://localhost:8080/actuator/health/rabbitMQ`

```json
{
  "status": "UP",
  "details": {
    "host": "localhost:5672",
    "vhost": "/",
    "channels": 5,
    "healthy": true
  }
}
```

### Vault Health

```java
@Component
public class VaultHealthIndicator implements HealthIndicator {
    // Checks Vault connectivity and credential freshness
}
```

Access at: `http://localhost:8080/actuator/health/vault`

```json
{
  "status": "UP",
  "details": {
    "credentialsValid": true,
    "expiresAt": "2024-12-27T12:00:00Z",
    "remainingTtl": "PT55M"
  }
}
```

---

## Dead Letter Queue

DLQ setup and management for failed messages.

### Configuration

```yaml
rabbitmq:
  dlq:
    enabled: true
    exchange: dlx
    queue-suffix: .dlq
    message-ttl: 24h
    max-retries: 3
```

### Setup

```java
@Autowired
private DLQManager dlqManager;

// Setup DLQ infrastructure for a queue
dlqManager.setupDLQ("order-events");
// Creates: order-events.dlq queue, bound to dlx exchange
```

### Processing DLQ Messages

```java
// Read messages from DLQ
consumer.consume(ConsumeOptions.builder()
    .queue("order-events.dlq")
    .autoAck(false)
    .build(),
    message -> {
        DLQMessage dlqMessage = DLQMessage.from(message);

        log.info("DLQ message - original exchange: {}, routing key: {}, error: {}",
            dlqMessage.originalExchange(),
            dlqMessage.originalRoutingKey(),
            dlqMessage.errorReason());

        // Retry or archive
        if (dlqMessage.retryCount() < 3) {
            publisher.publish(dlqMessage.originalExchange(),
                dlqMessage.originalRoutingKey(),
                message.getBody());
        }
    });
```

---

## Examples

See the `rabbitmq-examples` module for complete examples:

- `PublisherExample.java` - Publishing patterns
- `ConsumerExample.java` - Consuming patterns
- `DemoExample.java` - Full publish/consume flow

Run examples:

```bash
# Publisher example
mvn exec:java -pl rabbitmq-examples -Dexec.mainClass=com.shoppingcart.rabbitmq.examples.PublisherExample

# Consumer example
mvn exec:java -pl rabbitmq-examples -Dexec.mainClass=com.shoppingcart.rabbitmq.examples.ConsumerExample

# Demo (pub + sub)
make demo
```
