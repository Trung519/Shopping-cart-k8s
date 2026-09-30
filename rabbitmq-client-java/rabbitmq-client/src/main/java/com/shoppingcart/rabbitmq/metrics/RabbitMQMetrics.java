package com.shoppingcart.rabbitmq.metrics;

import io.micrometer.core.instrument.*;
import lombok.extern.slf4j.Slf4j;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Prometheus metrics for RabbitMQ client operations.
 * <p>
 * Tracks:
 * - Message publish/consume counts and latencies
 * - Connection pool metrics
 * - Circuit breaker states
 * - Error rates
 */
@Slf4j
public class RabbitMQMetrics {

    private static final String PREFIX = "rabbitmq_client";

    private final MeterRegistry registry;

    // Counters
    private final Counter messagesPublished;
    private final Counter messagesConsumed;
    private final Counter publishErrors;
    private final Counter consumeErrors;
    private final Counter connectionAttempts;
    private final Counter connectionFailures;

    // Timers
    private final Timer publishLatency;
    private final Timer consumeLatency;
    private final Timer connectionLatency;

    // Gauges
    private final AtomicInteger activeConnections = new AtomicInteger(0);
    private final AtomicInteger poolAvailable = new AtomicInteger(0);
    private final AtomicInteger activeConsumers = new AtomicInteger(0);

    public RabbitMQMetrics(MeterRegistry registry) {
        this.registry = registry;

        // Initialize counters
        this.messagesPublished = Counter.builder(PREFIX + "_messages_published_total")
                .description("Total number of messages published")
                .register(registry);

        this.messagesConsumed = Counter.builder(PREFIX + "_messages_consumed_total")
                .description("Total number of messages consumed")
                .register(registry);

        this.publishErrors = Counter.builder(PREFIX + "_publish_errors_total")
                .description("Total number of publish errors")
                .register(registry);

        this.consumeErrors = Counter.builder(PREFIX + "_consume_errors_total")
                .description("Total number of consume errors")
                .register(registry);

        this.connectionAttempts = Counter.builder(PREFIX + "_connection_attempts_total")
                .description("Total number of connection attempts")
                .register(registry);

        this.connectionFailures = Counter.builder(PREFIX + "_connection_failures_total")
                .description("Total number of connection failures")
                .register(registry);

        // Initialize timers
        this.publishLatency = Timer.builder(PREFIX + "_publish_latency_seconds")
                .description("Message publish latency")
                .register(registry);

        this.consumeLatency = Timer.builder(PREFIX + "_consume_latency_seconds")
                .description("Message consume/processing latency")
                .register(registry);

        this.connectionLatency = Timer.builder(PREFIX + "_connection_latency_seconds")
                .description("Connection establishment latency")
                .register(registry);

        // Initialize gauges
        Gauge.builder(PREFIX + "_connections_active", activeConnections, AtomicInteger::get)
                .description("Number of active connections")
                .register(registry);

        Gauge.builder(PREFIX + "_pool_available", poolAvailable, AtomicInteger::get)
                .description("Number of available connections in pool")
                .register(registry);

        Gauge.builder(PREFIX + "_consumers_active", activeConsumers, AtomicInteger::get)
                .description("Number of active consumers")
                .register(registry);
    }

    /**
     * Tracks a publish operation.
     *
     * @return Runnable to call when operation completes
     */
    public Runnable trackPublish(String exchange, String routingKey, int messageSize) {
        long startTime = System.nanoTime();

        Counter.builder(PREFIX + "_messages_published_total")
                .tag("exchange", exchange)
                .tag("routing_key", routingKey)
                .register(registry);

        DistributionSummary.builder(PREFIX + "_message_size_bytes")
                .tag("exchange", exchange)
                .register(registry)
                .record(messageSize);

        return () -> {
            long duration = System.nanoTime() - startTime;
            publishLatency.record(duration, TimeUnit.NANOSECONDS);
            messagesPublished.increment();

            Timer.builder(PREFIX + "_publish_latency_seconds")
                    .tag("exchange", exchange)
                    .register(registry)
                    .record(duration, TimeUnit.NANOSECONDS);
        };
    }

    /**
     * Tracks a consume operation.
     *
     * @return Runnable to call when processing completes
     */
    public Runnable trackConsume(String queue, boolean redelivered) {
        long startTime = System.nanoTime();

        if (redelivered) {
            Counter.builder(PREFIX + "_messages_redelivered_total")
                    .tag("queue", queue)
                    .register(registry)
                    .increment();
        }

        return () -> {
            long duration = System.nanoTime() - startTime;
            consumeLatency.record(duration, TimeUnit.NANOSECONDS);
            messagesConsumed.increment();

            Timer.builder(PREFIX + "_consume_latency_seconds")
                    .tag("queue", queue)
                    .register(registry)
                    .record(duration, TimeUnit.NANOSECONDS);
        };
    }

    /**
     * Records a publish error.
     */
    public void recordPublishError(String exchange, String routingKey) {
        publishErrors.increment();
        Counter.builder(PREFIX + "_publish_errors_total")
                .tag("exchange", exchange)
                .tag("routing_key", routingKey)
                .register(registry)
                .increment();
    }

    /**
     * Records a consume error.
     */
    public void recordConsumeError(String queue) {
        consumeErrors.increment();
        Counter.builder(PREFIX + "_consume_errors_total")
                .tag("queue", queue)
                .register(registry)
                .increment();
    }

    /**
     * Records a connection attempt.
     */
    public Runnable trackConnection(String host, int port) {
        long startTime = System.nanoTime();
        connectionAttempts.increment();

        return () -> {
            long duration = System.nanoTime() - startTime;
            connectionLatency.record(duration, TimeUnit.NANOSECONDS);
        };
    }

    /**
     * Records a connection failure.
     */
    public void recordConnectionFailure(String host, int port, String reason) {
        connectionFailures.increment();
        Counter.builder(PREFIX + "_connection_failures_total")
                .tag("host", host)
                .tag("port", String.valueOf(port))
                .tag("reason", reason)
                .register(registry)
                .increment();
    }

    /**
     * Updates pool metrics.
     */
    public void updatePoolMetrics(int active, int available) {
        activeConnections.set(active);
        poolAvailable.set(available);
    }

    /**
     * Updates consumer count.
     */
    public void updateConsumerCount(int count) {
        activeConsumers.set(count);
    }

    /**
     * Records circuit breaker state.
     */
    public void recordCircuitBreakerState(String name, String state) {
        Gauge.builder(PREFIX + "_circuit_breaker_state", () -> {
                    return switch (state) {
                        case "CLOSED" -> 0;
                        case "HALF_OPEN" -> 1;
                        case "OPEN" -> 2;
                        default -> -1;
                    };
                })
                .tag("name", name)
                .description("Circuit breaker state (0=closed, 1=half-open, 2=open)")
                .register(registry);
    }
}
