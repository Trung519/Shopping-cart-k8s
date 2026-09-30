package com.shoppingcart.rabbitmq.exception;

import lombok.Getter;

import java.time.Duration;

/**
 * Exception thrown when an operation is rejected because the circuit breaker is open.
 */
@Getter
public class CircuitBreakerOpenException extends RabbitMQException {

    private final String circuitName;
    private final Duration remainingTime;

    public CircuitBreakerOpenException(String circuitName) {
        super(String.format("Circuit breaker '%s' is open", circuitName));
        this.circuitName = circuitName;
        this.remainingTime = null;
    }

    public CircuitBreakerOpenException(String circuitName, Duration remainingTime) {
        super(String.format("Circuit breaker '%s' is open, remaining time: %s",
                circuitName, remainingTime));
        this.circuitName = circuitName;
        this.remainingTime = remainingTime;
    }
}
