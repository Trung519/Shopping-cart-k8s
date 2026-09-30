package com.shoppingcart.rabbitmq.exception;

import lombok.Getter;

/**
 * Exception thrown when publishing a message fails.
 */
@Getter
public class PublishException extends RabbitMQException {

    private final String exchange;
    private final String routingKey;

    public PublishException(String exchange, String routingKey, String message) {
        super(String.format("Failed to publish to exchange '%s' with routing key '%s': %s",
                exchange, routingKey, message));
        this.exchange = exchange;
        this.routingKey = routingKey;
    }

    public PublishException(String exchange, String routingKey, String message, Throwable cause) {
        super(String.format("Failed to publish to exchange '%s' with routing key '%s': %s",
                exchange, routingKey, message), cause);
        this.exchange = exchange;
        this.routingKey = routingKey;
    }
}
