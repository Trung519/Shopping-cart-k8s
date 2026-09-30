package com.shoppingcart.rabbitmq.exception;

import lombok.Getter;

/**
 * Exception thrown when consuming a message fails.
 */
@Getter
public class ConsumeException extends RabbitMQException {

    private final String queue;
    private final String messageId;

    public ConsumeException(String queue, String message) {
        super(String.format("Failed to consume from queue '%s': %s", queue, message));
        this.queue = queue;
        this.messageId = null;
    }

    public ConsumeException(String queue, String message, Throwable cause) {
        super(String.format("Failed to consume from queue '%s': %s", queue, message), cause);
        this.queue = queue;
        this.messageId = null;
    }

    public ConsumeException(String queue, String messageId, String message) {
        super(String.format("Failed to consume message '%s' from queue '%s': %s",
                messageId, queue, message));
        this.queue = queue;
        this.messageId = messageId;
    }

    public ConsumeException(String queue, String messageId, String message, Throwable cause) {
        super(String.format("Failed to consume message '%s' from queue '%s': %s",
                messageId, queue, message), cause);
        this.queue = queue;
        this.messageId = messageId;
    }
}
