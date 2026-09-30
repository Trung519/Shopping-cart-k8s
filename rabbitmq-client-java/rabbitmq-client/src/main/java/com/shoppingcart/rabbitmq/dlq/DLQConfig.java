package com.shoppingcart.rabbitmq.dlq;

import lombok.Builder;
import lombok.Data;

import java.time.Duration;

/**
 * Configuration for Dead Letter Queue setup.
 */
@Data
@Builder
public class DLQConfig {

    /**
     * Name of the source queue.
     */
    private String sourceQueue;

    /**
     * Name of the dead letter exchange.
     */
    @Builder.Default
    private String dlxExchange = "";

    /**
     * Name of the dead letter queue.
     */
    private String dlqQueue;

    /**
     * Routing key for dead letter messages.
     */
    @Builder.Default
    private String dlqRoutingKey = "";

    /**
     * Maximum number of retries before sending to DLQ.
     */
    @Builder.Default
    private int maxRetries = 3;

    /**
     * TTL for messages in the DLQ (null for no TTL).
     */
    private Duration messageTtl;

    /**
     * Maximum length of the DLQ (null for unlimited).
     */
    private Integer maxLength;

    /**
     * Whether the DLQ should be durable.
     */
    @Builder.Default
    private boolean durable = true;

    /**
     * Creates a default DLQ config for a source queue.
     */
    public static DLQConfig forQueue(String sourceQueue) {
        return DLQConfig.builder()
                .sourceQueue(sourceQueue)
                .dlqQueue(sourceQueue + ".dlq")
                .dlxExchange(sourceQueue + ".dlx")
                .dlqRoutingKey(sourceQueue + ".dead")
                .build();
    }
}
