package com.shoppingcart.rabbitmq.config;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

/**
 * Configuration properties for the RabbitMQ client library.
 * <p>
 * These properties can be configured via application.yml/properties or environment variables.
 * Environment variable format: RABBITMQ_HOST, RABBITMQ_PORT, etc.
 */
@Data
@Validated
@ConfigurationProperties(prefix = "rabbitmq")
public class RabbitMQProperties {

    /**
     * RabbitMQ server hostname.
     */
    @NotBlank
    private String host = "localhost";

    /**
     * RabbitMQ server port.
     */
    @Min(1)
    @Max(65535)
    private int port = 5672;

    /**
     * RabbitMQ virtual host.
     */
    private String vhost = "/";

    /**
     * Whether to use TLS for connections.
     */
    private boolean useTls = false;

    /**
     * Static username (used when Vault is disabled).
     */
    private String username = "guest";

    /**
     * Static password (used when Vault is disabled).
     */
    private String password = "guest";

    /**
     * Connection pool settings.
     */
    private Pool pool = new Pool();

    /**
     * Retry settings.
     */
    private Retry retry = new Retry();

    /**
     * Circuit breaker settings.
     */
    private CircuitBreaker circuitBreaker = new CircuitBreaker();

    /**
     * Vault integration settings.
     */
    private Vault vault = new Vault();

    @Data
    public static class Pool {
        /**
         * Number of connections in the pool.
         */
        @Min(1)
        private int size = 10;

        /**
         * Prefetch count for consumers.
         */
        @Min(0)
        private int prefetchCount = 10;

        /**
         * Connection heartbeat interval.
         */
        private Duration heartbeat = Duration.ofSeconds(60);

        /**
         * Maximum time a connection can be idle before being considered stale.
         */
        private Duration maxIdleTime = Duration.ofMinutes(10);

        /**
         * Timeout for acquiring a connection from the pool.
         */
        private Duration acquireTimeout = Duration.ofSeconds(30);
    }

    @Data
    public static class Retry {
        /**
         * Maximum number of retry attempts.
         */
        @Min(0)
        private int maxAttempts = 3;

        /**
         * Initial interval between retries.
         */
        private Duration initialInterval = Duration.ofSeconds(1);

        /**
         * Maximum interval between retries.
         */
        private Duration maxInterval = Duration.ofSeconds(30);

        /**
         * Multiplier for exponential backoff.
         */
        @Min(1)
        private double multiplier = 2.0;

        /**
         * Jitter factor for randomizing retry intervals (0.0 to 1.0).
         */
        @Min(0)
        @Max(1)
        private double jitterFactor = 0.1;
    }

    @Data
    public static class CircuitBreaker {
        /**
         * Whether circuit breaker is enabled.
         */
        private boolean enabled = true;

        /**
         * Number of failures before opening the circuit.
         */
        @Min(1)
        private int failureThreshold = 5;

        /**
         * Number of successes required to close the circuit from half-open state.
         */
        @Min(1)
        private int successThreshold = 2;

        /**
         * Time to wait before transitioning from open to half-open state.
         */
        private Duration timeout = Duration.ofSeconds(30);

        /**
         * Sliding window size for failure rate calculation.
         */
        @Min(1)
        private int slidingWindowSize = 10;

        /**
         * Failure rate threshold percentage (0-100).
         */
        @Min(0)
        @Max(100)
        private int failureRateThreshold = 50;
    }

    @Data
    public static class Vault {
        /**
         * Whether Vault integration is enabled.
         */
        private boolean enabled = true;

        /**
         * Vault role for RabbitMQ credentials.
         */
        private String role = "rabbitmq-role";

        /**
         * Vault backend path for RabbitMQ secrets.
         */
        private String backend = "rabbitmq";

        /**
         * Interval for credential renewal checks.
         */
        private Duration renewalInterval = Duration.ofMinutes(5);

        /**
         * Percentage of TTL at which to renew credentials (0.0 to 1.0).
         */
        @Min(0)
        @Max(1)
        private double renewalThreshold = 0.8;
    }
}
