package com.shoppingcart.rabbitmq.circuitbreaker;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.exception.CircuitBreakerOpenException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import lombok.extern.slf4j.Slf4j;

import java.time.Duration;

/**
 * Configuration for circuit breaker behavior using Resilience4j.
 */
@Slf4j
public class CircuitBreakerConfig {

    private final CircuitBreakerRegistry circuitBreakerRegistry;
    private final RabbitMQProperties.CircuitBreaker cbProperties;
    private final boolean enabled;

    public CircuitBreakerConfig(RabbitMQProperties properties) {
        this.cbProperties = properties.getCircuitBreaker();
        this.enabled = cbProperties.isEnabled();
        this.circuitBreakerRegistry = createRegistry();
    }

    private CircuitBreakerRegistry createRegistry() {
        if (!enabled) {
            return CircuitBreakerRegistry.ofDefaults();
        }

        io.github.resilience4j.circuitbreaker.CircuitBreakerConfig config =
                io.github.resilience4j.circuitbreaker.CircuitBreakerConfig.custom()
                        .failureRateThreshold(cbProperties.getFailureRateThreshold())
                        .slowCallRateThreshold(100) // Disable slow call detection
                        .waitDurationInOpenState(cbProperties.getTimeout())
                        .permittedNumberOfCallsInHalfOpenState(cbProperties.getSuccessThreshold())
                        .minimumNumberOfCalls(cbProperties.getFailureThreshold())
                        .slidingWindowType(io.github.resilience4j.circuitbreaker.CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                        .slidingWindowSize(cbProperties.getSlidingWindowSize())
                        .build();

        CircuitBreakerRegistry registry = CircuitBreakerRegistry.of(config);

        // Add event listeners
        registry.getEventPublisher().onEntryAdded(event -> {
            CircuitBreaker cb = event.getAddedEntry();
            cb.getEventPublisher()
                    .onStateTransition(e -> log.warn("Circuit breaker '{}' state changed: {} -> {}",
                            e.getCircuitBreakerName(),
                            e.getStateTransition().getFromState(),
                            e.getStateTransition().getToState()))
                    .onFailureRateExceeded(e -> log.warn("Circuit breaker '{}' failure rate exceeded: {}%",
                            e.getCircuitBreakerName(), e.getFailureRate()))
                    .onCallNotPermitted(e -> log.debug("Circuit breaker '{}' rejected call",
                            e.getCircuitBreakerName()));
        });

        return registry;
    }

    /**
     * Gets or creates a circuit breaker by name.
     */
    public CircuitBreaker getCircuitBreaker(String name) {
        return circuitBreakerRegistry.circuitBreaker(name);
    }

    /**
     * Gets the default circuit breaker.
     */
    public CircuitBreaker getDefaultCircuitBreaker() {
        return getCircuitBreaker("default");
    }

    /**
     * Checks if circuit breakers are enabled.
     */
    public boolean isEnabled() {
        return enabled;
    }

    /**
     * Gets the current state of a circuit breaker.
     */
    public CircuitBreaker.State getState(String name) {
        return getCircuitBreaker(name).getState();
    }

    /**
     * Manually opens a circuit breaker.
     */
    public void forceOpen(String name) {
        getCircuitBreaker(name).transitionToForcedOpenState();
        log.warn("Circuit breaker '{}' forced open", name);
    }

    /**
     * Resets a circuit breaker to closed state.
     */
    public void reset(String name) {
        getCircuitBreaker(name).reset();
        log.info("Circuit breaker '{}' reset to closed", name);
    }

    /**
     * Gets the circuit breaker registry.
     */
    public CircuitBreakerRegistry getRegistry() {
        return circuitBreakerRegistry;
    }

    /**
     * Wraps an exception if the circuit breaker is open.
     */
    public void checkCircuitBreaker(String name) {
        if (!enabled) {
            return;
        }

        CircuitBreaker cb = getCircuitBreaker(name);
        CircuitBreaker.State state = cb.getState();
        if (state == CircuitBreaker.State.OPEN || state == CircuitBreaker.State.FORCED_OPEN) {
            throw new CircuitBreakerOpenException(name, cbProperties.getTimeout());
        }
    }
}
