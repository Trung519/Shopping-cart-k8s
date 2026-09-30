package com.shoppingcart.rabbitmq.exception;

import lombok.Getter;

/**
 * Exception thrown when a connection to RabbitMQ fails.
 */
@Getter
public class ConnectionException extends RabbitMQException {

    private final String host;
    private final int port;
    private final String vhost;

    public ConnectionException(String host, int port, String vhost, String message) {
        super(String.format("Connection failed to %s:%d%s: %s", host, port, vhost, message));
        this.host = host;
        this.port = port;
        this.vhost = vhost;
    }

    public ConnectionException(String host, int port, String vhost, String message, Throwable cause) {
        super(String.format("Connection failed to %s:%d%s: %s", host, port, vhost, message), cause);
        this.host = host;
        this.port = port;
        this.vhost = vhost;
    }
}
