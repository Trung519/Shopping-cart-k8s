package com.shoppingcart.rabbitmq.dlq;

import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageProperties;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Represents a message from the Dead Letter Queue with parsed metadata.
 */
public record DLQMessage(
        Message originalMessage,
        String originalExchange,
        String originalRoutingKey,
        String errorMessage,
        Instant errorTimestamp,
        int retryCount,
        List<Map<String, Object>> deathHistory
) {
    // Header constants matching Go/Python implementations
    public static final String HEADER_X_DEATH = "x-death";
    public static final String HEADER_X_FIRST_DEATH_EXCHANGE = "x-first-death-exchange";
    public static final String HEADER_X_FIRST_DEATH_QUEUE = "x-first-death-queue";
    public static final String HEADER_X_FIRST_DEATH_REASON = "x-first-death-reason";
    public static final String HEADER_ORIGINAL_EXCHANGE = "x-original-exchange";
    public static final String HEADER_ORIGINAL_ROUTING_KEY = "x-original-routing-key";
    public static final String HEADER_ERROR_MESSAGE = "x-error-message";
    public static final String HEADER_ERROR_TIMESTAMP = "x-error-timestamp";
    public static final String HEADER_RETRY_COUNT = "x-retry-count";

    /**
     * Parses a DLQ message from a raw AMQP message.
     */
    @SuppressWarnings("unchecked")
    public static DLQMessage parse(Message message) {
        MessageProperties props = message.getMessageProperties();
        Map<String, Object> headers = props.getHeaders();

        // Get original exchange and routing key
        String originalExchange = getHeader(headers, HEADER_ORIGINAL_EXCHANGE, String.class)
                .or(() -> getHeader(headers, HEADER_X_FIRST_DEATH_EXCHANGE, String.class))
                .orElse("");

        String originalRoutingKey = getHeader(headers, HEADER_ORIGINAL_ROUTING_KEY, String.class)
                .orElse(props.getReceivedRoutingKey());

        // Get error info
        String errorMessage = getHeader(headers, HEADER_ERROR_MESSAGE, String.class)
                .or(() -> getHeader(headers, HEADER_X_FIRST_DEATH_REASON, String.class))
                .orElse("Unknown error");

        Instant errorTimestamp = getHeader(headers, HEADER_ERROR_TIMESTAMP, String.class)
                .map(Instant::parse)
                .orElse(Instant.now());

        // Get retry count
        int retryCount = getHeader(headers, HEADER_RETRY_COUNT, Number.class)
                .map(Number::intValue)
                .orElse(0);

        // Get death history
        List<Map<String, Object>> deathHistory = getHeader(headers, HEADER_X_DEATH, List.class)
                .orElse(List.of());

        // Calculate retry count from death history if not set
        if (retryCount == 0 && !deathHistory.isEmpty()) {
            retryCount = deathHistory.stream()
                    .mapToInt(death -> {
                        Object count = death.get("count");
                        return count instanceof Number ? ((Number) count).intValue() : 0;
                    })
                    .sum();
        }

        return new DLQMessage(
                message,
                originalExchange,
                originalRoutingKey,
                errorMessage,
                errorTimestamp,
                retryCount,
                deathHistory
        );
    }

    @SuppressWarnings("unchecked")
    private static <T> Optional<T> getHeader(Map<String, Object> headers, String key, Class<T> type) {
        Object value = headers.get(key);
        if (value != null && type.isInstance(value)) {
            return Optional.of((T) value);
        }
        return Optional.empty();
    }

    /**
     * Gets the message body as a string.
     */
    public String bodyAsString() {
        return new String(originalMessage.getBody());
    }

    /**
     * Gets the message ID.
     */
    public String messageId() {
        return originalMessage.getMessageProperties().getMessageId();
    }

    /**
     * Checks if the message can be retried.
     */
    public boolean canRetry(int maxRetries) {
        return retryCount < maxRetries;
    }
}
