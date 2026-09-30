package com.shoppingcart.rabbitmq.connection;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.exception.ConnectionException;
import com.shoppingcart.rabbitmq.vault.VaultCredentialManager;
import com.shoppingcart.rabbitmq.vault.VaultCredentials;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;

import jakarta.annotation.PreDestroy;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Manages RabbitMQ connections with Vault credential integration.
 * <p>
 * This component handles:
 * - Creating and configuring connection factories
 * - Integrating with Vault for dynamic credentials (when enabled)
 * - Using static credentials (when Vault is disabled)
 * - Connection event handling
 * - Graceful shutdown
 */
@Slf4j
public class ConnectionManager {

    private final RabbitMQProperties properties;
    private final VaultCredentialManager vaultCredentialManager;
    private final AtomicBoolean initialized = new AtomicBoolean(false);

    private CachingConnectionFactory connectionFactory;

    public ConnectionManager(RabbitMQProperties properties, VaultCredentialManager vaultCredentialManager) {
        this.properties = properties;
        this.vaultCredentialManager = vaultCredentialManager;
    }

    public ConnectionManager(RabbitMQProperties properties) {
        this(properties, null);
    }

    private boolean isVaultEnabled() {
        return properties.getVault().isEnabled() && vaultCredentialManager != null;
    }

    /**
     * Gets or creates the connection factory.
     *
     * @return The configured connection factory
     */
    public ConnectionFactory getConnectionFactory() {
        if (!initialized.get()) {
            synchronized (this) {
                if (!initialized.get()) {
                    initialize();
                }
            }
        }
        return connectionFactory;
    }

    /**
     * Initializes the connection factory with credentials.
     * Uses Vault credentials if enabled, otherwise uses static credentials from properties.
     */
    private void initialize() {
        log.info("Initializing RabbitMQ connection factory, host={}:{}, vhost={}, vault={}",
                properties.getHost(), properties.getPort(), properties.getVhost(), isVaultEnabled());

        try {
            String username;
            String password;

            if (isVaultEnabled()) {
                // Get credentials from Vault
                VaultCredentials credentials = vaultCredentialManager.getCredentials();
                username = credentials.username();
                password = credentials.password();
                log.info("Using Vault credentials for RabbitMQ connection");
            } else {
                // Use static credentials from properties
                username = properties.getUsername();
                password = properties.getPassword();
                log.info("Using static credentials for RabbitMQ connection");
            }

            // Create connection factory
            connectionFactory = new CachingConnectionFactory();
            connectionFactory.setHost(properties.getHost());
            connectionFactory.setPort(properties.getPort());
            connectionFactory.setVirtualHost(properties.getVhost());
            connectionFactory.setUsername(username);
            connectionFactory.setPassword(password);

            // Configure connection settings
            connectionFactory.setRequestedHeartBeat(
                    (int) properties.getPool().getHeartbeat().toSeconds());
            connectionFactory.setConnectionTimeout(
                    (int) properties.getPool().getAcquireTimeout().toMillis());

            // Configure channel caching
            connectionFactory.setCacheMode(CachingConnectionFactory.CacheMode.CHANNEL);
            connectionFactory.setChannelCacheSize(properties.getPool().getSize());

            // Enable publisher confirms
            connectionFactory.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.CORRELATED);
            connectionFactory.setPublisherReturns(true);

            // Add connection listener
            connectionFactory.addConnectionListener(connection -> {
                log.info("RabbitMQ connection established: {}", connection);
            });

            initialized.set(true);
            log.info("Successfully initialized RabbitMQ connection factory");

        } catch (Exception e) {
            log.error("Failed to initialize RabbitMQ connection factory", e);
            throw new ConnectionException(
                    properties.getHost(),
                    properties.getPort(),
                    properties.getVhost(),
                    "Failed to initialize connection factory",
                    e
            );
        }
    }

    /**
     * Refreshes the connection with new credentials from Vault.
     * No-op if Vault is disabled (static credentials don't need refresh).
     */
    public void refreshCredentials() {
        if (!isVaultEnabled()) {
            log.debug("Credential refresh skipped - Vault is disabled");
            return;
        }

        log.info("Refreshing RabbitMQ connection credentials");

        try {
            VaultCredentials credentials = vaultCredentialManager.fetchCredentials();

            if (connectionFactory != null) {
                connectionFactory.setUsername(credentials.username());
                connectionFactory.setPassword(credentials.password());
                connectionFactory.resetConnection();
                log.info("Successfully refreshed connection credentials");
            }
        } catch (Exception e) {
            log.error("Failed to refresh connection credentials", e);
            throw new ConnectionException(
                    properties.getHost(),
                    properties.getPort(),
                    properties.getVhost(),
                    "Failed to refresh credentials",
                    e
            );
        }
    }

    /**
     * Checks if the connection is healthy.
     */
    public boolean isHealthy() {
        if (connectionFactory == null) {
            return false;
        }

        try {
            var connection = connectionFactory.createConnection();
            boolean open = connection.isOpen();
            return open;
        } catch (Exception e) {
            log.warn("Health check failed", e);
            return false;
        }
    }

    /**
     * Closes the connection manager and releases resources.
     */
    @PreDestroy
    public void close() {
        log.info("Closing RabbitMQ connection manager");

        if (connectionFactory != null) {
            try {
                connectionFactory.destroy();
                log.info("Successfully closed connection factory");
            } catch (Exception e) {
                log.warn("Error closing connection factory", e);
            }
        }

        // Revoke Vault credentials (only if Vault is enabled)
        if (isVaultEnabled()) {
            vaultCredentialManager.revokeCredentials();
        }

        initialized.set(false);
    }

    /**
     * Gets connection statistics.
     */
    public ConnectionStats getStats() {
        if (connectionFactory == null) {
            return new ConnectionStats(0, 0, 0, false);
        }

        int channelCacheSize = 0;
        int idleChannels = 0;
        try {
            var cacheProperties = connectionFactory.getCacheProperties();
            channelCacheSize = Integer.parseInt(
                    cacheProperties.getOrDefault("channelCacheSize", "0").toString());
            idleChannels = Integer.parseInt(
                    cacheProperties.getOrDefault("idleChannelsNotTx", "0").toString());
        } catch (NullPointerException e) {
            // getCacheProperties() throws NPE before any channel is opened (Spring AMQP 3.1.0)
            log.debug("Unable to read RabbitMQ cache properties before any channel is opened", e);
        }

        return new ConnectionStats(
                channelCacheSize,
                channelCacheSize - idleChannels,
                idleChannels,
                isHealthy()
        );
    }

    /**
     * Connection statistics record.
     */
    public record ConnectionStats(
            int totalChannels,
            int activeChannels,
            int idleChannels,
            boolean healthy
    ) {}
}
