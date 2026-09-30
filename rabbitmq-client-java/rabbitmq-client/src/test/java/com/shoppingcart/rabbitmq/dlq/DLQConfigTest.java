package com.shoppingcart.rabbitmq.dlq;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class DLQConfigTest {

    @Test
    void forQueue_shouldCreateDefaultConfig() {
        var config = DLQConfig.forQueue("order-events");

        assertEquals("order-events", config.getSourceQueue());
        assertEquals("order-events.dlq", config.getDlqQueue());
        assertEquals("order-events.dlx", config.getDlxExchange());
        assertEquals("order-events.dead", config.getDlqRoutingKey());
        assertEquals(3, config.getMaxRetries());
        assertTrue(config.isDurable());
        assertNull(config.getMessageTtl());
        assertNull(config.getMaxLength());
    }

    @Test
    void builder_shouldSetAllFields() {
        var config = DLQConfig.builder()
                .sourceQueue("my-queue")
                .dlqQueue("my-queue-dlq")
                .dlxExchange("my-dlx")
                .dlqRoutingKey("dead")
                .maxRetries(5)
                .messageTtl(Duration.ofHours(24))
                .maxLength(10000)
                .durable(false)
                .build();

        assertEquals("my-queue", config.getSourceQueue());
        assertEquals("my-queue-dlq", config.getDlqQueue());
        assertEquals("my-dlx", config.getDlxExchange());
        assertEquals("dead", config.getDlqRoutingKey());
        assertEquals(5, config.getMaxRetries());
        assertEquals(Duration.ofHours(24), config.getMessageTtl());
        assertEquals(10000, config.getMaxLength());
        assertFalse(config.isDurable());
    }

    @Test
    void defaults_shouldHaveEmptyExchange() {
        var config = DLQConfig.builder()
                .sourceQueue("test")
                .dlqQueue("test.dlq")
                .build();

        assertEquals("", config.getDlxExchange());
        assertEquals("", config.getDlqRoutingKey());
    }
}
