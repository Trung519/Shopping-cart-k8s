package com.shoppingcart.rabbitmq.publisher;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.connection.ConnectionManager;
import com.shoppingcart.rabbitmq.exception.PublishException;
import com.shoppingcart.rabbitmq.metrics.RabbitMQMetrics;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

/**
 * Publisher for sending messages to RabbitMQ.
 * <p>
 * Features:
 * - Publisher confirms for reliable delivery
 * - JSON serialization
 * - Metrics tracking
 * - Retry integration
 */
@Slf4j
public class Publisher {

    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;
    private final RabbitMQMetrics metrics;
    private final RabbitMQProperties properties;

    public Publisher(ConnectionManager connectionManager,
                     ObjectMapper objectMapper,
                     RabbitMQMetrics metrics,
                     RabbitMQProperties properties) {
        this.rabbitTemplate = new RabbitTemplate(connectionManager.getConnectionFactory());
        this.objectMapper = objectMapper;
        this.metrics = metrics;
        this.properties = properties;

        // Configure template
        configureTemplate();
    }

    private void configureTemplate() {
        rabbitTemplate.setMandatory(true);
        rabbitTemplate.setReturnsCallback(returned -> {
            log.warn("Message returned: exchange={}, routingKey={}, replyCode={}, replyText={}",
                    returned.getExchange(),
                    returned.getRoutingKey(),
                    returned.getReplyCode(),
                    returned.getReplyText());
        });
    }

    /**
     * Publishes a message with default options.
     *
     * @param exchange   The exchange to publish to
     * @param routingKey The routing key
     * @param body       The message body (will be JSON serialized if not a byte array)
     */
    public void publish(String exchange, String routingKey, Object body) {
        publish(PublishOptions.of(exchange, routingKey), body);
    }

    /**
     * Publishes a message with custom options.
     *
     * @param options The publish options
     * @param body    The message body
     */
    public void publish(PublishOptions options, Object body) {
        var trackComplete = metrics != null ?
            metrics.trackPublish(options.getExchange(), options.getRoutingKey(), 0) : null;

        try {
            byte[] messageBody = serializeBody(body);
            Message message = createMessage(messageBody, options);

            log.debug("Publishing message to exchange='{}', routingKey='{}', size={}",
                    options.getExchange(), options.getRoutingKey(), messageBody.length);

            if (options.isWaitForConfirm()) {
                publishWithConfirm(options, message);
            } else {
                rabbitTemplate.send(options.getExchange(), options.getRoutingKey(), message);
            }

            log.debug("Successfully published message to exchange='{}', routingKey='{}'",
                    options.getExchange(), options.getRoutingKey());

            if (trackComplete != null) {
                trackComplete.run();
            }

        } catch (Exception e) {
            log.error("Failed to publish message to exchange='{}', routingKey='{}'",
                    options.getExchange(), options.getRoutingKey(), e);

            if (metrics != null) {
                metrics.recordPublishError(options.getExchange(), options.getRoutingKey());
            }

            throw new PublishException(options.getExchange(), options.getRoutingKey(),
                    "Failed to publish message", e);
        }
    }

    /**
     * Publishes a message and waits for confirmation.
     */
    private void publishWithConfirm(PublishOptions options, Message message) {
        rabbitTemplate.invoke(operations -> {
            operations.send(options.getExchange(), options.getRoutingKey(), message);
            boolean confirmed = operations.waitForConfirms(options.getConfirmTimeout());
            if (!confirmed) {
                throw new PublishException(options.getExchange(), options.getRoutingKey(),
                        "Publisher confirm timeout");
            }
            return null;
        });
    }

    /**
     * Serializes the message body.
     */
    private byte[] serializeBody(Object body) {
        if (body instanceof byte[] bytes) {
            return bytes;
        }
        if (body instanceof String str) {
            return str.getBytes(StandardCharsets.UTF_8);
        }
        try {
            return objectMapper.writeValueAsBytes(body);
        } catch (JsonProcessingException e) {
            throw new PublishException("", "", "Failed to serialize message body", e);
        }
    }

    /**
     * Creates an AMQP message with the given body and options.
     */
    private Message createMessage(byte[] body, PublishOptions options) {
        MessageProperties props = new MessageProperties();
        props.setContentType(options.getContentType());
        props.setContentEncoding(options.getContentEncoding());
        props.setDeliveryMode(options.getDeliveryMode());
        props.setMessageId(UUID.randomUUID().toString());
        props.setTimestamp(new java.util.Date());

        if (options.getPriority() != null) {
            props.setPriority(options.getPriority());
        }
        if (options.getExpiration() != null) {
            props.setExpiration(options.getExpiration());
        }
        if (options.getCorrelationId() != null) {
            props.setCorrelationId(options.getCorrelationId());
        }
        if (options.getReplyTo() != null) {
            props.setReplyTo(options.getReplyTo());
        }

        // Add custom headers
        options.getHeaders().forEach(props::setHeader);

        return new Message(body, props);
    }

    /**
     * Declares an exchange if it doesn't exist.
     */
    public void declareExchange(String name, ExchangeType type, boolean durable, boolean autoDelete) {
        Exchange exchange = switch (type) {
            case DIRECT -> new DirectExchange(name, durable, autoDelete);
            case TOPIC -> new TopicExchange(name, durable, autoDelete);
            case FANOUT -> new FanoutExchange(name, durable, autoDelete);
            case HEADERS -> new HeadersExchange(name, durable, autoDelete);
        };

        rabbitTemplate.execute(channel -> {
            channel.exchangeDeclare(name, type.name().toLowerCase(), durable, autoDelete, null);
            return null;
        });

        log.info("Declared exchange: name={}, type={}, durable={}", name, type, durable);
    }

    /**
     * Exchange types.
     */
    public enum ExchangeType {
        DIRECT, TOPIC, FANOUT, HEADERS
    }
}
