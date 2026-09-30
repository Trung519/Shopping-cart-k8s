package com.shoppingcart.rabbitmq.consumer;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.connection.ConnectionManager;
import com.shoppingcart.rabbitmq.exception.ConsumeException;
import com.shoppingcart.rabbitmq.metrics.RabbitMQMetrics;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;
import org.springframework.amqp.rabbit.listener.api.ChannelAwareMessageListener;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Consumer for receiving messages from RabbitMQ.
 * <p>
 * Features:
 * - Manual or auto acknowledgment
 * - Prefetch control
 * - Metrics tracking
 * - Graceful shutdown
 */
@Slf4j
public class Consumer {

    private final ConnectionManager connectionManager;
    private final RabbitTemplate rabbitTemplate;
    private final RabbitMQMetrics metrics;
    private final RabbitMQProperties properties;
    private final Map<String, SimpleMessageListenerContainer> containers = new ConcurrentHashMap<>();

    public Consumer(ConnectionManager connectionManager,
                    RabbitMQMetrics metrics,
                    RabbitMQProperties properties) {
        this.connectionManager = connectionManager;
        this.rabbitTemplate = new RabbitTemplate(connectionManager.getConnectionFactory());
        this.metrics = metrics;
        this.properties = properties;
    }

    /**
     * Starts consuming from a queue with the given handler.
     *
     * @param options The consume options
     * @param handler The message handler
     * @return A consumer ID that can be used to stop consuming
     */
    public String consume(ConsumeOptions options, MessageHandler handler) {
        String consumerId = options.getConsumerTag() != null ?
                options.getConsumerTag() : UUID.randomUUID().toString();

        log.info("Starting consumer for queue='{}', consumerId={}", options.getQueue(), consumerId);

        try {
            // Declare queue if needed
            declareQueue(options.getQueue(), options.getQueueOptions());

            // Create listener container
            SimpleMessageListenerContainer container = new SimpleMessageListenerContainer();
            container.setConnectionFactory(connectionManager.getConnectionFactory());
            container.setQueueNames(options.getQueue());
            container.setPrefetchCount(options.getPrefetchCount());
            container.setAcknowledgeMode(options.isAutoAck() ?
                    AcknowledgeMode.AUTO : AcknowledgeMode.MANUAL);
            container.setConsumerTagStrategy(q -> consumerId);

            // Set message listener
            container.setMessageListener((ChannelAwareMessageListener) (message, channel) -> {
                var trackComplete = metrics != null ?
                        metrics.trackConsume(options.getQueue(), message.getMessageProperties().isRedelivered())
                        : null;

                try {
                    log.debug("Received message from queue='{}', messageId={}",
                            options.getQueue(),
                            message.getMessageProperties().getMessageId());

                    handler.handle(message);

                    // Manual ack
                    if (!options.isAutoAck() && channel != null) {
                        channel.basicAck(message.getMessageProperties().getDeliveryTag(), false);
                    }

                    if (trackComplete != null) {
                        trackComplete.run();
                    }

                } catch (Exception e) {
                    log.error("Error processing message from queue='{}', messageId={}",
                            options.getQueue(),
                            message.getMessageProperties().getMessageId(), e);

                    if (metrics != null) {
                        metrics.recordConsumeError(options.getQueue());
                    }

                    // Manual nack
                    if (!options.isAutoAck() && channel != null) {
                        channel.basicNack(
                                message.getMessageProperties().getDeliveryTag(),
                                false,
                                options.isRequeueOnFailure()
                        );
                    }

                    throw new ConsumeException(options.getQueue(),
                            message.getMessageProperties().getMessageId(),
                            "Message handling failed", e);
                }
            });

            // Start consuming
            container.start();
            containers.put(consumerId, container);

            log.info("Consumer started for queue='{}', consumerId={}", options.getQueue(), consumerId);
            return consumerId;

        } catch (Exception e) {
            log.error("Failed to start consumer for queue='{}'", options.getQueue(), e);
            throw new ConsumeException(options.getQueue(), "Failed to start consumer", e);
        }
    }

    /**
     * Starts consuming with default options.
     */
    public String consume(String queue, MessageHandler handler) {
        return consume(ConsumeOptions.of(queue), handler);
    }

    /**
     * Stops a consumer.
     *
     * @param consumerId The consumer ID returned from consume()
     */
    public void stop(String consumerId) {
        SimpleMessageListenerContainer container = containers.remove(consumerId);
        if (container != null) {
            log.info("Stopping consumer: {}", consumerId);
            container.stop();
            container.destroy();
        }
    }

    /**
     * Stops all consumers.
     */
    public void stopAll() {
        log.info("Stopping all consumers");
        containers.forEach((id, container) -> {
            container.stop();
            container.destroy();
        });
        containers.clear();
    }

    /**
     * Declares a queue.
     */
    public void declareQueue(String name, ConsumeOptions.QueueOptions options) {
        rabbitTemplate.execute(channel -> {
            channel.queueDeclare(
                    name,
                    options.isDurable(),
                    options.isExclusive(),
                    options.isAutoDelete(),
                    options.getArguments()
            );
            return null;
        });
        log.info("Declared queue: name={}, durable={}", name, options.isDurable());
    }

    /**
     * Binds a queue to an exchange.
     */
    public void bindQueue(String queue, String exchange, String routingKey) {
        rabbitTemplate.execute(channel -> {
            channel.queueBind(queue, exchange, routingKey);
            return null;
        });
        log.info("Bound queue '{}' to exchange '{}' with routing key '{}'",
                queue, exchange, routingKey);
    }

    /**
     * Gets the number of active consumers.
     */
    public int activeConsumerCount() {
        return containers.size();
    }

    /**
     * Checks if a consumer is active.
     */
    public boolean isActive(String consumerId) {
        SimpleMessageListenerContainer container = containers.get(consumerId);
        return container != null && container.isRunning();
    }
}
