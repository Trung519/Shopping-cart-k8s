package com.shoppingcart.rabbitmq.exception;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class ExceptionTest {

    @Test
    void rabbitMQException_shouldContainMessage() {
        var ex = new RabbitMQException("Test error");
        assertEquals("Test error", ex.getMessage());
    }

    @Test
    void rabbitMQException_shouldContainCause() {
        var cause = new RuntimeException("Cause");
        var ex = new RabbitMQException("Test error", cause);

        assertEquals("Test error", ex.getMessage());
        assertEquals(cause, ex.getCause());
    }

    @Test
    void connectionException_shouldContainConnectionDetails() {
        var ex = new ConnectionException("localhost", 5672, "/", "Connection refused");

        assertEquals("localhost", ex.getHost());
        assertEquals(5672, ex.getPort());
        assertEquals("/", ex.getVhost());
        assertTrue(ex.getMessage().contains("localhost"));
        assertTrue(ex.getMessage().contains("5672"));
        assertTrue(ex.getMessage().contains("Connection refused"));
    }

    @Test
    void connectionException_shouldContainCause() {
        var cause = new RuntimeException("Network error");
        var ex = new ConnectionException("localhost", 5672, "/", "Connection failed", cause);

        assertEquals(cause, ex.getCause());
    }

    @Test
    void publishException_shouldContainPublishDetails() {
        var ex = new PublishException("events", "order.created", "Timeout");

        assertEquals("events", ex.getExchange());
        assertEquals("order.created", ex.getRoutingKey());
        assertTrue(ex.getMessage().contains("events"));
        assertTrue(ex.getMessage().contains("order.created"));
        assertTrue(ex.getMessage().contains("Timeout"));
    }

    @Test
    void consumeException_shouldContainQueueDetails() {
        var ex = new ConsumeException("order-events", "Processing failed");

        assertEquals("order-events", ex.getQueue());
        assertNull(ex.getMessageId());
        assertTrue(ex.getMessage().contains("order-events"));
    }

    @Test
    void consumeException_shouldContainMessageId() {
        var ex = new ConsumeException("order-events", "msg-123", "Invalid format");

        assertEquals("order-events", ex.getQueue());
        assertEquals("msg-123", ex.getMessageId());
        assertTrue(ex.getMessage().contains("msg-123"));
    }

    @Test
    void circuitBreakerOpenException_shouldContainCircuitName() {
        var ex = new CircuitBreakerOpenException("publish-circuit");

        assertEquals("publish-circuit", ex.getCircuitName());
        assertNull(ex.getRemainingTime());
        assertTrue(ex.getMessage().contains("publish-circuit"));
    }

    @Test
    void circuitBreakerOpenException_shouldContainRemainingTime() {
        var remaining = Duration.ofSeconds(30);
        var ex = new CircuitBreakerOpenException("publish-circuit", remaining);

        assertEquals("publish-circuit", ex.getCircuitName());
        assertEquals(remaining, ex.getRemainingTime());
        assertTrue(ex.getMessage().contains("30"));
    }
}
