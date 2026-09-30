package com.shoppingcart.rabbitmq.dlq;

import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class DLQMessageTest {

    @Test
    void parse_shouldExtractBasicFields() {
        var props = new MessageProperties();
        props.setMessageId("msg-123");
        props.setReceivedRoutingKey("order.created");

        var headers = new HashMap<String, Object>();
        headers.put(DLQMessage.HEADER_ORIGINAL_EXCHANGE, "events");
        headers.put(DLQMessage.HEADER_ORIGINAL_ROUTING_KEY, "order.created");
        headers.put(DLQMessage.HEADER_ERROR_MESSAGE, "Processing failed");
        headers.put(DLQMessage.HEADER_RETRY_COUNT, 2);
        props.getHeaders().putAll(headers);

        var message = new Message("{\"test\":\"data\"}".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertEquals("events", dlqMessage.originalExchange());
        assertEquals("order.created", dlqMessage.originalRoutingKey());
        assertEquals("Processing failed", dlqMessage.errorMessage());
        assertEquals(2, dlqMessage.retryCount());
    }

    @Test
    void parse_shouldUseFirstDeathHeadersAsFallback() {
        var props = new MessageProperties();
        props.setReceivedRoutingKey("dead");

        var headers = new HashMap<String, Object>();
        headers.put(DLQMessage.HEADER_X_FIRST_DEATH_EXCHANGE, "events");
        headers.put(DLQMessage.HEADER_X_FIRST_DEATH_REASON, "rejected");
        props.getHeaders().putAll(headers);

        var message = new Message("test".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertEquals("events", dlqMessage.originalExchange());
        assertEquals("rejected", dlqMessage.errorMessage());
    }

    @Test
    void parse_shouldCalculateRetryCountFromDeathHistory() {
        var props = new MessageProperties();

        var death1 = Map.<String, Object>of("count", 3, "queue", "queue1");
        var death2 = Map.<String, Object>of("count", 2, "queue", "queue2");

        var headers = new HashMap<String, Object>();
        headers.put(DLQMessage.HEADER_X_DEATH, List.of(death1, death2));
        props.getHeaders().putAll(headers);

        var message = new Message("test".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertEquals(5, dlqMessage.retryCount());
    }

    @Test
    void bodyAsString_shouldReturnStringBody() {
        var props = new MessageProperties();
        var message = new Message("{\"orderId\":\"123\"}".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertEquals("{\"orderId\":\"123\"}", dlqMessage.bodyAsString());
    }

    @Test
    void messageId_shouldReturnMessageId() {
        var props = new MessageProperties();
        props.setMessageId("msg-456");
        var message = new Message("test".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertEquals("msg-456", dlqMessage.messageId());
    }

    @Test
    void canRetry_shouldReturnTrueWhenBelowMax() {
        var props = new MessageProperties();
        props.getHeaders().put(DLQMessage.HEADER_RETRY_COUNT, 2);
        var message = new Message("test".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertTrue(dlqMessage.canRetry(3));
        assertFalse(dlqMessage.canRetry(2));
        assertFalse(dlqMessage.canRetry(1));
    }

    @Test
    void parse_shouldHandleTimestamp() {
        var props = new MessageProperties();
        var timestamp = Instant.now().toString();

        var headers = new HashMap<String, Object>();
        headers.put(DLQMessage.HEADER_ERROR_TIMESTAMP, timestamp);
        props.getHeaders().putAll(headers);

        var message = new Message("test".getBytes(), props);
        var dlqMessage = DLQMessage.parse(message);

        assertNotNull(dlqMessage.errorTimestamp());
    }
}
