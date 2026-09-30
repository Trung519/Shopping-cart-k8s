package com.shoppingcart.rabbitmq.exception;

/**
 * Base exception for all RabbitMQ client errors.
 */
public class RabbitMQException extends RuntimeException {

    public RabbitMQException(String message) {
        super(message);
    }

    public RabbitMQException(String message, Throwable cause) {
        super(message, cause);
    }

    public RabbitMQException(Throwable cause) {
        super(cause);
    }
}
