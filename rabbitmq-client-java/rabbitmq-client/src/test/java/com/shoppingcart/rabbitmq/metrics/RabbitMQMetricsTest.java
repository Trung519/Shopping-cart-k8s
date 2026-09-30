package com.shoppingcart.rabbitmq.metrics;

import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class RabbitMQMetricsTest {

    private MeterRegistry registry;
    private RabbitMQMetrics metrics;

    @BeforeEach
    void setUp() {
        registry = new SimpleMeterRegistry();
        metrics = new RabbitMQMetrics(registry);
    }

    @Test
    void trackPublish_shouldRecordMetrics() {
        var complete = metrics.trackPublish("events", "order.created", 100);
        complete.run();

        var counter = registry.find("rabbitmq_client_messages_published_total").counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void trackConsume_shouldRecordMetrics() {
        var complete = metrics.trackConsume("order-events", false);
        complete.run();

        var counter = registry.find("rabbitmq_client_messages_consumed_total").counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void trackConsume_shouldRecordRedelivered() {
        var complete = metrics.trackConsume("order-events", true);
        complete.run();

        var counter = registry.find("rabbitmq_client_messages_redelivered_total")
                .tag("queue", "order-events")
                .counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void recordPublishError_shouldIncrementCounter() {
        metrics.recordPublishError("events", "order.created");
        metrics.recordPublishError("events", "order.created");

        var counter = registry.find("rabbitmq_client_publish_errors_total").counter();
        assertNotNull(counter);
        assertEquals(2.0, counter.count());
    }

    @Test
    void recordConsumeError_shouldIncrementCounter() {
        metrics.recordConsumeError("order-events");

        var counter = registry.find("rabbitmq_client_consume_errors_total").counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void trackConnection_shouldRecordMetrics() {
        var complete = metrics.trackConnection("localhost", 5672);
        complete.run();

        var counter = registry.find("rabbitmq_client_connection_attempts_total").counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void recordConnectionFailure_shouldIncrementCounter() {
        metrics.recordConnectionFailure("localhost", 5672, "Connection refused");

        var counter = registry.find("rabbitmq_client_connection_failures_total").counter();
        assertNotNull(counter);
        assertEquals(1.0, counter.count());
    }

    @Test
    void updatePoolMetrics_shouldSetGauges() {
        metrics.updatePoolMetrics(10, 5);

        var activeGauge = registry.find("rabbitmq_client_connections_active").gauge();
        var availableGauge = registry.find("rabbitmq_client_pool_available").gauge();

        assertNotNull(activeGauge);
        assertNotNull(availableGauge);
        assertEquals(10.0, activeGauge.value());
        assertEquals(5.0, availableGauge.value());
    }

    @Test
    void updateConsumerCount_shouldSetGauge() {
        metrics.updateConsumerCount(3);

        var gauge = registry.find("rabbitmq_client_consumers_active").gauge();
        assertNotNull(gauge);
        assertEquals(3.0, gauge.value());
    }
}
