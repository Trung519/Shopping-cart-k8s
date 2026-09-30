package com.shoppingcart.rabbitmq.consumer;

import lombok.Builder;
import lombok.Data;

import java.util.HashMap;
import java.util.Map;

/**
 * Options for consuming messages from RabbitMQ.
 */
@Data
@Builder
public class ConsumeOptions {

    /**
     * The queue to consume from.
     */
    private String queue;

    /**
     * Consumer tag for identification.
     */
    private String consumerTag;

    /**
     * Whether to auto-acknowledge messages.
     */
    @Builder.Default
    private boolean autoAck = false;

    /**
     * Whether the queue is exclusive to this consumer.
     */
    @Builder.Default
    private boolean exclusive = false;

    /**
     * Prefetch count (QoS).
     */
    @Builder.Default
    private int prefetchCount = 10;

    /**
     * Whether to requeue messages on failure.
     */
    @Builder.Default
    private boolean requeueOnFailure = true;

    /**
     * Maximum number of retries before sending to DLQ.
     */
    @Builder.Default
    private int maxRetries = 3;

    /**
     * Consumer arguments.
     */
    @Builder.Default
    private Map<String, Object> arguments = new HashMap<>();

    /**
     * Queue declaration options.
     */
    @Builder.Default
    private QueueOptions queueOptions = QueueOptions.defaults();

    /**
     * Creates default consume options for a queue.
     */
    public static ConsumeOptions of(String queue) {
        return ConsumeOptions.builder()
                .queue(queue)
                .build();
    }

    /**
     * Queue declaration options.
     */
    @Data
    @Builder
    public static class QueueOptions {
        /**
         * Whether the queue should be durable.
         */
        @Builder.Default
        private boolean durable = true;

        /**
         * Whether the queue is exclusive.
         */
        @Builder.Default
        private boolean exclusive = false;

        /**
         * Whether the queue should auto-delete.
         */
        @Builder.Default
        private boolean autoDelete = false;

        /**
         * Queue arguments (TTL, max length, etc.).
         */
        @Builder.Default
        private Map<String, Object> arguments = new HashMap<>();

        public static QueueOptions defaults() {
            return QueueOptions.builder().build();
        }
    }
}
