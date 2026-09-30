# RabbitMQ Client Library (Java)

Production-ready RabbitMQ client library with HashiCorp Vault integration for dynamic credential management.

## Features

- **Vault Integration**: Dynamic credentials from HashiCorp Vault with automatic renewal
- **Connection Pooling**: Efficient connection management with Spring AMQP
- **Publisher Confirms**: Reliable message delivery with confirmation support
- **Consumer Support**: Manual/auto acknowledgment with prefetch control
- **Circuit Breaker**: Resilience4j integration for fault tolerance
- **Retry Logic**: Exponential backoff with jitter
- **Metrics**: Micrometer/Prometheus metrics
- **Health Checks**: Spring Boot Actuator health indicators
- **Dead Letter Queue**: DLQ setup and management
- **CLI Tools**: Command-line publisher and consumer

## Requirements

- Java 21+
- Maven 3.9+
- RabbitMQ 3.12+
- HashiCorp Vault (optional, for dynamic credentials)

## Quick Start

### Add Dependency

```xml
<dependency>
    <groupId>com.shoppingcart</groupId>
    <artifactId>rabbitmq-client</artifactId>
    <version>1.0.0-SNAPSHOT</version>
</dependency>
```

### Configuration

```yaml
rabbitmq:
  host: localhost
  port: 5672
  vhost: /

  vault:
    enabled: true
    role: rabbitmq-role
    backend: rabbitmq

spring:
  cloud:
    vault:
      uri: http://localhost:8200
      token: ${VAULT_TOKEN}
```

### Publishing Messages

```java
@Autowired
private Publisher publisher;

// Simple publish
publisher.publish("events", "order.created", Map.of(
    "orderId", "ORD-123",
    "amount", 99.99
));

// With options
PublishOptions options = PublishOptions.builder()
    .exchange("events")
    .routingKey("order.created")
    .priority(5)
    .build();
publisher.publish(options, orderData);
```

### Consuming Messages

```java
@Autowired
private Consumer consumer;

ConsumeOptions options = ConsumeOptions.builder()
    .queue("order-events")
    .autoAck(false)
    .prefetchCount(10)
    .build();

consumer.consume(options, message -> {
    String body = new String(message.getBody());
    // Process message
    log.info("Received: {}", body);
});
```

## CLI Tools

### Publisher

```bash
# Build CLI
mvn package -pl rabbitmq-cli -am

# Publish message
java -jar rabbitmq-cli/target/rabbitmq-cli-1.0.0-SNAPSHOT-publisher.jar \
  -e events order.created '{"orderId":"123"}'
```

### Consumer

```bash
java -jar rabbitmq-cli/target/rabbitmq-cli-1.0.0-SNAPSHOT-consumer.jar \
  order-events --json-output
```

## Building

```bash
# Build all modules
mvn clean install

# Run tests
mvn test

# Run integration tests (requires Docker)
mvn verify -P integration-tests

# Generate coverage report
mvn jacoco:report
```

## Module Structure

| Module | Description |
|--------|-------------|
| `rabbitmq-client` | Core library with all components |
| `rabbitmq-cli` | Command-line tools |
| `rabbitmq-examples` | Example applications |

## Configuration Reference

| Property | Default | Description |
|----------|---------|-------------|
| `rabbitmq.host` | `localhost` | RabbitMQ hostname |
| `rabbitmq.port` | `5672` | RabbitMQ port |
| `rabbitmq.vhost` | `/` | Virtual host |
| `rabbitmq.pool.size` | `10` | Connection pool size |
| `rabbitmq.retry.max-attempts` | `3` | Max retry attempts |
| `rabbitmq.circuit-breaker.enabled` | `true` | Enable circuit breaker |

## Health Endpoints

When using Spring Boot Actuator:

- `/actuator/health/rabbitMQ` - RabbitMQ connection health
- `/actuator/health/vault` - Vault credential health
- `/actuator/prometheus` - Prometheus metrics

## License

MIT License
