package com.shoppingcart.rabbitmq.publisher;

import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.MessageDeliveryMode;

import static org.junit.jupiter.api.Assertions.*;

class PublishOptionsTest {

    @Test
    void defaults_shouldHaveCorrectValues() {
        var options = PublishOptions.defaults();

        assertEquals("", options.getExchange());
        assertEquals("", options.getRoutingKey());
        assertEquals(MessageDeliveryMode.PERSISTENT, options.getDeliveryMode());
        assertEquals("application/json", options.getContentType());
        assertEquals("UTF-8", options.getContentEncoding());
        assertTrue(options.isWaitForConfirm());
        assertEquals(5000, options.getConfirmTimeout());
        assertFalse(options.isMandatory());
        assertNotNull(options.getHeaders());
        assertTrue(options.getHeaders().isEmpty());
    }

    @Test
    void of_shouldCreateWithExchangeAndRoutingKey() {
        var options = PublishOptions.of("events", "order.created");

        assertEquals("events", options.getExchange());
        assertEquals("order.created", options.getRoutingKey());
    }

    @Test
    void builder_shouldSetAllFields() {
        var options = PublishOptions.builder()
                .exchange("my-exchange")
                .routingKey("my.key")
                .deliveryMode(MessageDeliveryMode.NON_PERSISTENT)
                .contentType("text/plain")
                .priority(5)
                .expiration("60000")
                .correlationId("corr-123")
                .replyTo("reply-queue")
                .waitForConfirm(false)
                .mandatory(true)
                .build();

        assertEquals("my-exchange", options.getExchange());
        assertEquals("my.key", options.getRoutingKey());
        assertEquals(MessageDeliveryMode.NON_PERSISTENT, options.getDeliveryMode());
        assertEquals("text/plain", options.getContentType());
        assertEquals(5, options.getPriority());
        assertEquals("60000", options.getExpiration());
        assertEquals("corr-123", options.getCorrelationId());
        assertEquals("reply-queue", options.getReplyTo());
        assertFalse(options.isWaitForConfirm());
        assertTrue(options.isMandatory());
    }

    @Test
    void withHeader_shouldAddHeader() {
        var options = PublishOptions.defaults()
                .withHeader("key1", "value1")
                .withHeader("key2", 123);

        assertEquals("value1", options.getHeaders().get("key1"));
        assertEquals(123, options.getHeaders().get("key2"));
    }

    @Test
    void withHeader_shouldOverwriteExistingHeader() {
        var options = PublishOptions.defaults()
                .withHeader("key", "value1")
                .withHeader("key", "value2");

        assertEquals("value2", options.getHeaders().get("key"));
    }
}
