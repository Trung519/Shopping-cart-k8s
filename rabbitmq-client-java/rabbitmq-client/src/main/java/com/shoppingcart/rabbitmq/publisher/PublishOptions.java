package com.shoppingcart.rabbitmq.publisher;

import lombok.Builder;
import lombok.Data;
import org.springframework.amqp.core.MessageDeliveryMode;

import java.util.HashMap;
import java.util.Map;

/**
 * Options for publishing messages to RabbitMQ.
 */
@Data
@Builder
public class PublishOptions {

    /**
     * The exchange to publish to.
     */
    @Builder.Default
    private String exchange = "";

    /**
     * The routing key for the message.
     */
    @Builder.Default
    private String routingKey = "";

    /**
     * Message delivery mode (PERSISTENT or NON_PERSISTENT).
     */
    @Builder.Default
    private MessageDeliveryMode deliveryMode = MessageDeliveryMode.PERSISTENT;

    /**
     * Content type of the message body.
     */
    @Builder.Default
    private String contentType = "application/json";

    /**
     * Content encoding.
     */
    @Builder.Default
    private String contentEncoding = "UTF-8";

    /**
     * Message priority (0-9).
     */
    private Integer priority;

    /**
     * Message expiration in milliseconds.
     */
    private String expiration;

    /**
     * Correlation ID for request-reply pattern.
     */
    private String correlationId;

    /**
     * Reply-to queue for RPC.
     */
    private String replyTo;

    /**
     * Custom message headers.
     */
    @Builder.Default
    private Map<String, Object> headers = new HashMap<>();

    /**
     * Whether to wait for publisher confirms.
     */
    @Builder.Default
    private boolean waitForConfirm = true;

    /**
     * Timeout for publisher confirms in milliseconds.
     */
    @Builder.Default
    private long confirmTimeout = 5000;

    /**
     * Whether to use mandatory flag (returns unroutable messages).
     */
    @Builder.Default
    private boolean mandatory = false;

    /**
     * Creates default publish options.
     */
    public static PublishOptions defaults() {
        return PublishOptions.builder().build();
    }

    /**
     * Creates publish options for a specific exchange and routing key.
     */
    public static PublishOptions of(String exchange, String routingKey) {
        return PublishOptions.builder()
                .exchange(exchange)
                .routingKey(routingKey)
                .build();
    }

    /**
     * Adds a custom header.
     */
    public PublishOptions withHeader(String key, Object value) {
        this.headers.put(key, value);
        return this;
    }
}
