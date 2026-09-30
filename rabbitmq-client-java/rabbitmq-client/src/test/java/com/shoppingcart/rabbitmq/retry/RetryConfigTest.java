package com.shoppingcart.rabbitmq.retry;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class RetryConfigTest {

    private RabbitMQProperties properties;
    private RetryConfig retryConfig;

    @BeforeEach
    void setUp() {
        properties = new RabbitMQProperties();
        properties.getRetry().setMaxAttempts(3);
        properties.getRetry().setInitialInterval(Duration.ofMillis(100));
        properties.getRetry().setMaxInterval(Duration.ofSeconds(1));
        properties.getRetry().setMultiplier(2.0);
        retryConfig = new RetryConfig(properties);
    }

    @Test
    void getDefaultRetry_shouldReturnRetryInstance() {
        var retry = retryConfig.getDefaultRetry();

        assertNotNull(retry);
        assertEquals("default", retry.getName());
    }

    @Test
    void getRetry_shouldReturnNamedRetryInstance() {
        var retry = retryConfig.getRetry("custom-retry");

        assertNotNull(retry);
        assertEquals("custom-retry", retry.getName());
    }

    @Test
    void getRetry_shouldReturnSameInstanceForSameName() {
        var retry1 = retryConfig.getRetry("test");
        var retry2 = retryConfig.getRetry("test");

        assertSame(retry1, retry2);
    }

    @Test
    void createCustomRetry_shouldCreateWithCustomSettings() {
        var retry = retryConfig.createCustomRetry("custom", 5, Duration.ofMillis(50));

        assertNotNull(retry);
        assertEquals("custom", retry.getName());
    }

    @Test
    void getRegistry_shouldReturnRegistry() {
        var registry = retryConfig.getRegistry();

        assertNotNull(registry);
    }
}
