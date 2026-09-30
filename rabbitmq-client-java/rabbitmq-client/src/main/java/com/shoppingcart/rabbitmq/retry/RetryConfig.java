package com.shoppingcart.rabbitmq.retry;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.AmqpException;

import java.net.ConnectException;
import java.time.Duration;
import java.util.concurrent.TimeoutException;

/**
 * Configuration for retry behavior using Resilience4j.
 */
@Slf4j
public class RetryConfig {

    private final RetryRegistry retryRegistry;
    private final RabbitMQProperties.Retry retryProperties;

    public RetryConfig(RabbitMQProperties properties) {
        this.retryProperties = properties.getRetry();
        this.retryRegistry = createRegistry();
    }

    private RetryRegistry createRegistry() {
        io.github.resilience4j.retry.RetryConfig config = io.github.resilience4j.retry.RetryConfig.custom()
                .maxAttempts(retryProperties.getMaxAttempts())
                .intervalFunction(attempt -> {
                    // Exponential backoff with jitter
                    double delay = retryProperties.getInitialInterval().toMillis() *
                            Math.pow(retryProperties.getMultiplier(), attempt - 1);

                    // Apply max interval cap
                    delay = Math.min(delay, retryProperties.getMaxInterval().toMillis());

                    // Apply jitter
                    double jitter = delay * retryProperties.getJitterFactor() * Math.random();
                    return (long) (delay + jitter);
                })
                .retryOnException(this::isRetryable)
                .failAfterMaxAttempts(true)
                .build();

        RetryRegistry registry = RetryRegistry.of(config);

        // Add event listeners
        registry.getEventPublisher().onEntryAdded(event -> {
            Retry retry = event.getAddedEntry();
            retry.getEventPublisher()
                    .onRetry(e -> log.warn("Retry attempt {} for '{}'",
                            e.getNumberOfRetryAttempts(), e.getName()))
                    .onError(e -> log.error("Retry exhausted for '{}' after {} attempts",
                            e.getName(), e.getNumberOfRetryAttempts()))
                    .onSuccess(e -> log.debug("Operation succeeded for '{}' after {} attempts",
                            e.getName(), e.getNumberOfRetryAttempts()));
        });

        return registry;
    }

    /**
     * Determines if an exception is retryable.
     */
    private boolean isRetryable(Throwable throwable) {
        return throwable instanceof AmqpException ||
                throwable instanceof ConnectException ||
                throwable instanceof TimeoutException ||
                (throwable.getCause() != null && isRetryable(throwable.getCause()));
    }

    /**
     * Gets or creates a retry instance by name.
     */
    public Retry getRetry(String name) {
        return retryRegistry.retry(name);
    }

    /**
     * Gets the default retry instance.
     */
    public Retry getDefaultRetry() {
        return getRetry("default");
    }

    /**
     * Creates a custom retry with specific settings.
     */
    public Retry createCustomRetry(String name, int maxAttempts, Duration initialInterval) {
        io.github.resilience4j.retry.RetryConfig config = io.github.resilience4j.retry.RetryConfig.custom()
                .maxAttempts(maxAttempts)
                .waitDuration(initialInterval)
                .retryOnException(this::isRetryable)
                .build();

        return retryRegistry.retry(name, config);
    }

    /**
     * Gets the retry registry.
     */
    public RetryRegistry getRegistry() {
        return retryRegistry;
    }
}
