package com.shoppingcart.rabbitmq.dlq;

import com.shoppingcart.rabbitmq.connection.ConnectionManager;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import com.shoppingcart.rabbitmq.publisher.PublishOptions;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/**
 * Manager for Dead Letter Queue operations.
 * <p>
 * Handles:
 * - DLQ infrastructure setup
 * - Routing failed messages to DLQ
 * - Retrying messages from DLQ
 * - Discarding messages
 */
@Slf4j
public class DLQManager {

    private final RabbitTemplate rabbitTemplate;
    private final Publisher publisher;

    public DLQManager(ConnectionManager connectionManager, Publisher publisher) {
        this.rabbitTemplate = new RabbitTemplate(connectionManager.getConnectionFactory());
        this.publisher = publisher;
    }

    /**
     * Sets up DLQ infrastructure for a queue.
     */
    public void setupDLQ(DLQConfig config) {
        log.info("Setting up DLQ for queue '{}': dlx='{}', dlq='{}'",
                config.getSourceQueue(), config.getDlxExchange(), config.getDlqQueue());

        rabbitTemplate.execute(channel -> {
            // Declare DLX exchange
            channel.exchangeDeclare(
                    config.getDlxExchange(),
                    "direct",
                    config.isDurable()
            );

            // Build DLQ arguments
            Map<String, Object> dlqArgs = new HashMap<>();
            if (config.getMessageTtl() != null) {
                dlqArgs.put("x-message-ttl", config.getMessageTtl().toMillis());
            }
            if (config.getMaxLength() != null) {
                dlqArgs.put("x-max-length", config.getMaxLength());
            }

            // Declare DLQ
            channel.queueDeclare(
                    config.getDlqQueue(),
                    config.isDurable(),
                    false,
                    false,
                    dlqArgs
            );

            // Bind DLQ to DLX
            channel.queueBind(
                    config.getDlqQueue(),
                    config.getDlxExchange(),
                    config.getDlqRoutingKey()
            );

            // Update source queue with DLX settings
            Map<String, Object> sourceArgs = new HashMap<>();
            sourceArgs.put("x-dead-letter-exchange", config.getDlxExchange());
            sourceArgs.put("x-dead-letter-routing-key", config.getDlqRoutingKey());

            // Note: Source queue must be declared with these args when created
            log.info("DLQ setup complete. Source queue should have args: {}", sourceArgs);

            return null;
        });
    }

    /**
     * Sends a failed message to the DLQ with error metadata.
     */
    public void sendToDLQ(DLQConfig config, Message message, String errorMessage) {
        MessageProperties props = message.getMessageProperties();

        // Get current retry count
        int retryCount = 0;
        Object retryHeader = props.getHeader(DLQMessage.HEADER_RETRY_COUNT);
        if (retryHeader instanceof Number) {
            retryCount = ((Number) retryHeader).intValue();
        }

        // Add error metadata
        Map<String, Object> headers = new HashMap<>(props.getHeaders());
        headers.put(DLQMessage.HEADER_ORIGINAL_EXCHANGE, props.getReceivedExchange());
        headers.put(DLQMessage.HEADER_ORIGINAL_ROUTING_KEY, props.getReceivedRoutingKey());
        headers.put(DLQMessage.HEADER_ERROR_MESSAGE, errorMessage);
        headers.put(DLQMessage.HEADER_ERROR_TIMESTAMP, Instant.now().toString());
        headers.put(DLQMessage.HEADER_RETRY_COUNT, retryCount + 1);

        PublishOptions options = PublishOptions.builder()
                .exchange(config.getDlxExchange())
                .routingKey(config.getDlqRoutingKey())
                .headers(headers)
                .build();

        publisher.publish(options, message.getBody());

        log.info("Sent message to DLQ: queue='{}', messageId='{}', retryCount={}",
                config.getDlqQueue(), props.getMessageId(), retryCount + 1);
    }

    /**
     * Retries a message from the DLQ by republishing to original destination.
     */
    public void retry(DLQMessage dlqMessage) {
        log.info("Retrying DLQ message: messageId='{}', originalExchange='{}', originalRoutingKey='{}'",
                dlqMessage.messageId(), dlqMessage.originalExchange(), dlqMessage.originalRoutingKey());

        // Update retry count
        Map<String, Object> headers = new HashMap<>(
                dlqMessage.originalMessage().getMessageProperties().getHeaders());
        headers.put(DLQMessage.HEADER_RETRY_COUNT, dlqMessage.retryCount());

        PublishOptions options = PublishOptions.builder()
                .exchange(dlqMessage.originalExchange())
                .routingKey(dlqMessage.originalRoutingKey())
                .headers(headers)
                .build();

        publisher.publish(options, dlqMessage.originalMessage().getBody());
    }

    /**
     * Discards a message from the DLQ (acknowledges without processing).
     */
    public void discard(DLQMessage dlqMessage, String reason) {
        log.warn("Discarding DLQ message: messageId='{}', reason='{}'",
                dlqMessage.messageId(), reason);
        // Message will be acked by the caller
    }

    /**
     * Gets the count of messages in a DLQ.
     */
    public long getQueueCount(String queueName) {
        return rabbitTemplate.execute(channel -> {
            var declareOk = channel.queueDeclarePassive(queueName);
            return (long) declareOk.getMessageCount();
        });
    }

    /**
     * Purges all messages from a DLQ.
     */
    public void purge(String queueName) {
        log.warn("Purging all messages from queue '{}'", queueName);
        rabbitTemplate.execute(channel -> {
            channel.queuePurge(queueName);
            return null;
        });
    }
}
