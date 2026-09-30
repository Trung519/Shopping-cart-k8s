package com.shoppingcart.rabbitmq.config;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class RabbitMQPropertiesTest {

    private Validator validator;

    @BeforeEach
    void setUp() {
        ValidatorFactory factory = Validation.buildDefaultValidatorFactory();
        validator = factory.getValidator();
    }

    @Test
    void defaultValues_shouldBeSet() {
        var props = new RabbitMQProperties();

        assertEquals("localhost", props.getHost());
        assertEquals(5672, props.getPort());
        assertEquals("/", props.getVhost());
        assertFalse(props.isUseTls());
    }

    @Test
    void poolDefaults_shouldBeSet() {
        var props = new RabbitMQProperties();
        var pool = props.getPool();

        assertEquals(10, pool.getSize());
        assertEquals(10, pool.getPrefetchCount());
        assertEquals(Duration.ofSeconds(60), pool.getHeartbeat());
        assertEquals(Duration.ofMinutes(10), pool.getMaxIdleTime());
        assertEquals(Duration.ofSeconds(30), pool.getAcquireTimeout());
    }

    @Test
    void retryDefaults_shouldBeSet() {
        var props = new RabbitMQProperties();
        var retry = props.getRetry();

        assertEquals(3, retry.getMaxAttempts());
        assertEquals(Duration.ofSeconds(1), retry.getInitialInterval());
        assertEquals(Duration.ofSeconds(30), retry.getMaxInterval());
        assertEquals(2.0, retry.getMultiplier());
        assertEquals(0.1, retry.getJitterFactor());
    }

    @Test
    void circuitBreakerDefaults_shouldBeSet() {
        var props = new RabbitMQProperties();
        var cb = props.getCircuitBreaker();

        assertTrue(cb.isEnabled());
        assertEquals(5, cb.getFailureThreshold());
        assertEquals(2, cb.getSuccessThreshold());
        assertEquals(Duration.ofSeconds(30), cb.getTimeout());
        assertEquals(10, cb.getSlidingWindowSize());
        assertEquals(50, cb.getFailureRateThreshold());
    }

    @Test
    void vaultDefaults_shouldBeSet() {
        var props = new RabbitMQProperties();
        var vault = props.getVault();

        assertTrue(vault.isEnabled());
        assertEquals("rabbitmq-role", vault.getRole());
        assertEquals("rabbitmq", vault.getBackend());
        assertEquals(Duration.ofMinutes(5), vault.getRenewalInterval());
        assertEquals(0.8, vault.getRenewalThreshold());
    }

    @Test
    void validation_shouldFailForBlankHost() {
        var props = new RabbitMQProperties();
        props.setHost("");

        var violations = validator.validate(props);
        assertFalse(violations.isEmpty());
    }

    @Test
    void validation_shouldFailForInvalidPort() {
        var props = new RabbitMQProperties();
        props.setPort(0);

        var violations = validator.validate(props);
        assertFalse(violations.isEmpty());
    }

    @Test
    void validation_shouldFailForPortTooHigh() {
        var props = new RabbitMQProperties();
        props.setPort(70000);

        var violations = validator.validate(props);
        assertFalse(violations.isEmpty());
    }

    @Test
    void validation_shouldPassForValidConfig() {
        var props = new RabbitMQProperties();
        props.setHost("rabbitmq.example.com");
        props.setPort(5672);

        var violations = validator.validate(props);
        assertTrue(violations.isEmpty());
    }
}
