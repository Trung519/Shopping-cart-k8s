package com.shoppingcart.rabbitmq.consumer;

import org.springframework.amqp.core.Message;

/**
 * Functional interface for handling consumed messages.
 */
@FunctionalInterface
public interface MessageHandler {

    /**
     * Handles a consumed message.
     *
     * @param message The consumed message
     * @throws Exception if handling fails (message will be nacked/requeued based on config)
     */
    void handle(Message message) throws Exception;
}
