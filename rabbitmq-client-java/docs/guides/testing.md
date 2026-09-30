# Testing Guide

This guide covers testing strategies and how to run tests for the RabbitMQ client library.

## Table of Contents

- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [Writing Tests](#writing-tests)
- [Test Configuration](#test-configuration)
- [Code Coverage](#code-coverage)

---

## Test Structure

```
rabbitmq-client/
└── src/test/java/com/shoppingcart/rabbitmq/
    ├── config/
    │   └── RabbitMQPropertiesTest.java
    ├── consumer/
    │   └── ConsumeOptionsTest.java
    ├── publisher/
    │   └── PublishOptionsTest.java
    ├── vault/
    │   └── VaultCredentialsTest.java
    ├── circuitbreaker/
    │   └── CircuitBreakerConfigTest.java
    ├── retry/
    │   └── RetryConfigTest.java
    ├── metrics/
    │   └── RabbitMQMetricsTest.java
    ├── dlq/
    │   ├── DLQConfigTest.java
    │   └── DLQMessageTest.java
    ├── exception/
    │   └── ExceptionTest.java
    └── integration/
        └── (integration tests with Testcontainers)
```

---

## Running Tests

### All Tests

```bash
# Run all unit tests
mvn test

# Run all tests including integration tests
mvn verify

# Run with specific profile
mvn test -P unit-tests
mvn verify -P integration-tests
```

### Specific Test Classes

```bash
# Run single test class
mvn test -Dtest=PublishOptionsTest

# Run specific test method
mvn test -Dtest=PublishOptionsTest#testBuilderDefaults

# Run tests matching pattern
mvn test -Dtest="*OptionsTest"
```

### Using Make

```bash
# Unit tests only
make test

# All tests with integration
make test-integration

# Tests with coverage report
make test-coverage
```

---

## Unit Tests

Unit tests run without external dependencies using mocks.

### Example: PublishOptionsTest

```java
package com.shoppingcart.rabbitmq.publisher;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class PublishOptionsTest {

    @Test
    void testBuilderDefaults() {
        PublishOptions options = PublishOptions.builder()
            .exchange("events")
            .routingKey("test.event")
            .build();

        assertThat(options.getExchange()).isEqualTo("events");
        assertThat(options.getRoutingKey()).isEqualTo("test.event");
        assertThat(options.isPersistent()).isTrue();  // default
        assertThat(options.getPriority()).isEqualTo(0);  // default
    }

    @Test
    void testBuilderWithAllOptions() {
        PublishOptions options = PublishOptions.builder()
            .exchange("events")
            .routingKey("order.created")
            .persistent(true)
            .mandatory(true)
            .priority(5)
            .expiration(Duration.ofMinutes(10))
            .contentType("application/json")
            .header("x-trace-id", "abc-123")
            .build();

        assertThat(options.isMandatory()).isTrue();
        assertThat(options.getPriority()).isEqualTo(5);
        assertThat(options.getHeaders()).containsEntry("x-trace-id", "abc-123");
    }

    @Test
    void testBuilderValidation() {
        assertThatThrownBy(() -> PublishOptions.builder().build())
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Exchange is required");
    }
}
```

### Example: Testing with Mocks

```java
package com.shoppingcart.rabbitmq.publisher;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class PublisherTest {

    @Mock
    private RabbitTemplate rabbitTemplate;

    @Mock
    private RabbitMQMetrics metrics;

    @InjectMocks
    private Publisher publisher;

    @Test
    void testPublishSuccess() {
        // Given
        PublishOptions options = PublishOptions.builder()
            .exchange("events")
            .routingKey("test.event")
            .build();
        String message = "{\"test\": true}";

        when(metrics.trackPublish(anyString(), anyString(), anyInt()))
            .thenReturn(() -> {});

        // When
        publisher.publish(options, message);

        // Then
        verify(rabbitTemplate).convertAndSend(
            eq("events"),
            eq("test.event"),
            eq(message),
            any()
        );
    }
}
```

---

## Integration Tests

Integration tests use Testcontainers for real RabbitMQ and Vault instances.

### Prerequisites

- Docker installed and running
- Sufficient resources for containers

### Example: Integration Test

```java
package com.shoppingcart.rabbitmq.integration;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.testcontainers.containers.RabbitMQContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.*;

@Testcontainers
@SpringBootTest
class PublishConsumeIntegrationTest {

    @Container
    static RabbitMQContainer rabbitmq = new RabbitMQContainer("rabbitmq:3.12-management-alpine");

    @Autowired
    private Publisher publisher;

    @Autowired
    private Consumer consumer;

    @Test
    void testPublishAndConsume() throws Exception {
        // Setup
        String queue = "test-queue-" + System.currentTimeMillis();
        String exchange = "test-exchange";
        CountDownLatch latch = new CountDownLatch(1);
        StringBuilder received = new StringBuilder();

        // Declare infrastructure
        consumer.declareQueue(queue, QueueOptions.defaults());
        consumer.bindQueue(queue, exchange, "#");

        // Start consumer
        consumer.consume(ConsumeOptions.builder()
            .queue(queue)
            .autoAck(true)
            .build(),
            message -> {
                received.append(new String(message.getBody()));
                latch.countDown();
            });

        // Publish
        publisher.publish(exchange, "test.event", "{\"test\": true}");

        // Wait for message
        boolean completed = latch.await(5, TimeUnit.SECONDS);

        // Assert
        assertThat(completed).isTrue();
        assertThat(received.toString()).contains("test");
    }
}
```

### Testcontainers Configuration

```java
@TestConfiguration
public class TestContainersConfig {

    @Container
    static RabbitMQContainer rabbitmq = new RabbitMQContainer("rabbitmq:3.12-management-alpine")
        .withExposedPorts(5672, 15672);

    @Container
    static VaultContainer vault = new VaultContainer("hashicorp/vault:1.15")
        .withVaultToken("root-token")
        .withSecretInVault("secret/rabbitmq",
            "username=guest",
            "password=guest");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("rabbitmq.host", rabbitmq::getHost);
        registry.add("rabbitmq.port", rabbitmq::getAmqpPort);
        registry.add("spring.cloud.vault.uri", vault::getHttpHostAddress);
    }
}
```

---

## Writing Tests

### Best Practices

1. **Test One Thing**: Each test should verify a single behavior
2. **Descriptive Names**: Use clear method names that describe what's being tested
3. **Arrange-Act-Assert**: Structure tests with clear sections
4. **Mock External Dependencies**: Use Mockito for unit tests
5. **Use Testcontainers**: For integration tests with real services

### Test Naming Convention

```java
@Test
void shouldPublishMessage_whenOptionsAreValid() { }

@Test
void shouldThrowException_whenExchangeIsNull() { }

@Test
void shouldRetryOnFailure_whenRetryConfigured() { }
```

### AssertJ Assertions

```java
// Prefer AssertJ over JUnit assertions
import static org.assertj.core.api.Assertions.*;

// Basic assertions
assertThat(result).isNotNull();
assertThat(result.getMessage()).isEqualTo("expected");
assertThat(list).hasSize(3).contains("a", "b");

// Exception assertions
assertThatThrownBy(() -> publisher.publish(null, "key", "msg"))
    .isInstanceOf(IllegalArgumentException.class)
    .hasMessageContaining("Exchange");

// Soft assertions (report all failures)
SoftAssertions.assertSoftly(softly -> {
    softly.assertThat(options.getExchange()).isEqualTo("events");
    softly.assertThat(options.getRoutingKey()).isEqualTo("test");
    softly.assertThat(options.getPriority()).isEqualTo(5);
});
```

---

## Test Configuration

### application-test.yaml

```yaml
rabbitmq:
  host: localhost
  port: 5672
  vault:
    enabled: false
  username: guest
  password: guest

logging:
  level:
    com.shoppingcart.rabbitmq: DEBUG
    org.springframework.amqp: INFO
```

### Test Properties

```java
@SpringBootTest(properties = {
    "rabbitmq.host=localhost",
    "rabbitmq.vault.enabled=false"
})
class MyTest {
    // ...
}
```

---

## Code Coverage

### Generate Coverage Report

```bash
# Run tests with coverage
mvn test jacoco:report

# View report
open target/site/jacoco/index.html
```

### Coverage Thresholds

The build enforces minimum coverage thresholds:

```xml
<configuration>
    <rules>
        <rule>
            <element>BUNDLE</element>
            <limits>
                <limit>
                    <counter>LINE</counter>
                    <value>COVEREDRATIO</value>
                    <minimum>0.80</minimum>
                </limit>
                <limit>
                    <counter>BRANCH</counter>
                    <value>COVEREDRATIO</value>
                    <minimum>0.70</minimum>
                </limit>
            </limits>
        </rule>
    </rules>
</configuration>
```

### Excluding Classes from Coverage

```xml
<configuration>
    <excludes>
        <exclude>**/*Config.class</exclude>
        <exclude>**/*Application.class</exclude>
    </excludes>
</configuration>
```

---

## Troubleshooting

### Common Issues

**Tests hang waiting for RabbitMQ**
```bash
# Ensure Docker is running
docker ps

# Check if container started
docker logs <container-id>
```

**Connection refused in tests**
```bash
# Verify ports are exposed
docker ps -a | grep rabbitmq

# Check container health
docker inspect <container-id> | grep Health
```

**Flaky integration tests**
- Add `@DirtiesContext` to reset Spring context
- Use unique queue names per test
- Increase timeouts for CI environments

### Debug Mode

```bash
# Run tests with debug output
mvn test -X

# Remote debug
mvn test -Dmaven.surefire.debug
```
