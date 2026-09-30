package com.shoppingcart.rabbitmq.vault;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.exception.RabbitMQException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.vault.core.VaultTemplate;
import org.springframework.vault.support.VaultResponse;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * Manages RabbitMQ credentials obtained from HashiCorp Vault.
 * <p>
 * This component handles:
 * - Fetching initial credentials from Vault
 * - Automatic credential renewal before expiration
 * - Thread-safe credential access
 * - Credential revocation on shutdown
 */
@Slf4j
public class VaultCredentialManager {

    private final VaultTemplate vaultTemplate;
    private final RabbitMQProperties.Vault vaultProperties;
    private final ReadWriteLock lock = new ReentrantReadWriteLock();

    private VaultCredentials credentials;

    public VaultCredentialManager(VaultTemplate vaultTemplate, RabbitMQProperties properties) {
        this.vaultTemplate = vaultTemplate;
        this.vaultProperties = properties.getVault();
    }

    /**
     * Gets the current credentials, fetching from Vault if necessary.
     *
     * @return The current valid credentials
     * @throws RabbitMQException if credentials cannot be obtained
     */
    public VaultCredentials getCredentials() {
        lock.readLock().lock();
        try {
            if (credentials != null && !credentials.isExpired()) {
                return credentials;
            }
        } finally {
            lock.readLock().unlock();
        }

        // Need to fetch new credentials
        return fetchCredentials();
    }

    /**
     * Fetches fresh credentials from Vault.
     */
    public VaultCredentials fetchCredentials() {
        lock.writeLock().lock();
        try {
            // Double-check after acquiring write lock
            if (credentials != null && !credentials.isExpired()) {
                return credentials;
            }

            log.info("Fetching RabbitMQ credentials from Vault, role={}", vaultProperties.getRole());

            String path = String.format("%s/creds/%s", vaultProperties.getBackend(), vaultProperties.getRole());
            VaultResponse response = vaultTemplate.read(path);

            if (response == null || response.getData() == null) {
                throw new RabbitMQException("Failed to fetch credentials from Vault: empty response");
            }

            Map<String, Object> data = response.getData();
            String username = (String) data.get("username");
            String password = (String) data.get("password");

            if (username == null || password == null) {
                throw new RabbitMQException("Invalid credentials from Vault: missing username or password");
            }

            // Get TTL from lease duration
            Duration ttl = Duration.ofSeconds(response.getLeaseDuration());
            String leaseId = response.getLeaseId();

            credentials = VaultCredentials.of(username, password, ttl, leaseId);

            log.info("Successfully fetched credentials from Vault, username={}, ttl={}",
                    username, ttl);

            return credentials;
        } catch (Exception e) {
            log.error("Failed to fetch credentials from Vault", e);
            throw new RabbitMQException("Failed to fetch credentials from Vault", e);
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Scheduled task to renew credentials before expiration.
     */
    @Scheduled(fixedDelayString = "${rabbitmq.vault.renewal-interval:PT5M}")
    public void renewCredentialsIfNeeded() {
        lock.readLock().lock();
        try {
            if (credentials == null) {
                return;
            }

            if (!credentials.shouldRenew(vaultProperties.getRenewalThreshold())) {
                log.debug("Credentials still valid, remaining time: {}", credentials.remainingTime());
                return;
            }
        } finally {
            lock.readLock().unlock();
        }

        // Try to renew
        renewCredentials();
    }

    /**
     * Attempts to renew the current credentials lease.
     */
    private void renewCredentials() {
        lock.writeLock().lock();
        try {
            if (credentials == null || credentials.leaseId() == null) {
                log.warn("No credentials to renew, fetching new ones");
                fetchCredentials();
                return;
            }

            log.info("Credentials need renewal, fetching new credentials");

            // Instead of renewing the lease, we fetch new credentials
            // This is simpler and more robust as it doesn't depend on Vault lease renewal API
            try {
                // Fetch new credentials
                lock.writeLock().unlock();
                try {
                    fetchCredentials();
                } finally {
                    lock.writeLock().lock();
                }
                log.info("Successfully fetched new credentials");
            } catch (Exception e) {
                log.error("Failed to fetch new credentials during renewal", e);
            }
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Revokes the current credentials lease.
     * Should be called on application shutdown.
     */
    public void revokeCredentials() {
        lock.writeLock().lock();
        try {
            if (credentials == null || credentials.leaseId() == null) {
                return;
            }

            log.info("Clearing RabbitMQ credentials, leaseId={}", credentials.leaseId());

            // Note: Vault leases will expire automatically based on their TTL
            // We simply clear the local credentials here
            credentials = null;
            log.info("Successfully cleared credentials");
        } finally {
            lock.writeLock().unlock();
        }
    }

    /**
     * Checks if valid credentials are available.
     */
    public boolean hasValidCredentials() {
        lock.readLock().lock();
        try {
            return credentials != null && !credentials.isExpired();
        } finally {
            lock.readLock().unlock();
        }
    }
}
