package com.shoppingcart.rabbitmq.circuitbreaker;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.exception.CircuitBreakerOpenException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

class CircuitBreakerConfigTest {

    private RabbitMQProperties properties;
    private CircuitBreakerConfig circuitBreakerConfig;

    @BeforeEach
    void setUp() {
        properties = new RabbitMQProperties();
        properties.getCircuitBreaker().setEnabled(true);
        properties.getCircuitBreaker().setFailureThreshold(5);
        properties.getCircuitBreaker().setSuccessThreshold(2);
        properties.getCircuitBreaker().setTimeout(Duration.ofSeconds(30));
        circuitBreakerConfig = new CircuitBreakerConfig(properties);
    }

    @Test
    void isEnabled_shouldReturnTrueWhenEnabled() {
        assertTrue(circuitBreakerConfig.isEnabled());
    }

    @Test
    void isEnabled_shouldReturnFalseWhenDisabled() {
        properties.getCircuitBreaker().setEnabled(false);
        var config = new CircuitBreakerConfig(properties);

        assertFalse(config.isEnabled());
    }

    @Test
    void getDefaultCircuitBreaker_shouldReturnCircuitBreaker() {
        var cb = circuitBreakerConfig.getDefaultCircuitBreaker();

        assertNotNull(cb);
        assertEquals("default", cb.getName());
    }

    @Test
    void getCircuitBreaker_shouldReturnNamedCircuitBreaker() {
        var cb = circuitBreakerConfig.getCircuitBreaker("custom");

        assertNotNull(cb);
        assertEquals("custom", cb.getName());
    }

    @Test
    void getCircuitBreaker_shouldReturnSameInstanceForSameName() {
        var cb1 = circuitBreakerConfig.getCircuitBreaker("test");
        var cb2 = circuitBreakerConfig.getCircuitBreaker("test");

        assertSame(cb1, cb2);
    }

    @Test
    void getState_shouldReturnClosedInitially() {
        var state = circuitBreakerConfig.getState("new-circuit");

        assertEquals(CircuitBreaker.State.CLOSED, state);
    }

    @Test
    void forceOpen_shouldOpenCircuit() {
        circuitBreakerConfig.forceOpen("test-circuit");

        assertEquals(CircuitBreaker.State.FORCED_OPEN, circuitBreakerConfig.getState("test-circuit"));
    }

    @Test
    void reset_shouldCloseCircuit() {
        circuitBreakerConfig.forceOpen("test-circuit");
        circuitBreakerConfig.reset("test-circuit");

        assertEquals(CircuitBreaker.State.CLOSED, circuitBreakerConfig.getState("test-circuit"));
    }

    @Test
    void checkCircuitBreaker_shouldThrowWhenOpen() {
        circuitBreakerConfig.forceOpen("test-circuit");

        assertThrows(CircuitBreakerOpenException.class, () ->
            circuitBreakerConfig.checkCircuitBreaker("test-circuit")
        );
    }

    @Test
    void checkCircuitBreaker_shouldNotThrowWhenClosed() {
        assertDoesNotThrow(() ->
            circuitBreakerConfig.checkCircuitBreaker("test-circuit")
        );
    }

    @Test
    void checkCircuitBreaker_shouldNotThrowWhenDisabled() {
        properties.getCircuitBreaker().setEnabled(false);
        var config = new CircuitBreakerConfig(properties);
        config.forceOpen("test");

        assertDoesNotThrow(() ->
            config.checkCircuitBreaker("test")
        );
    }

    @Test
    void getRegistry_shouldReturnRegistry() {
        var registry = circuitBreakerConfig.getRegistry();

        assertNotNull(registry);
    }
}
