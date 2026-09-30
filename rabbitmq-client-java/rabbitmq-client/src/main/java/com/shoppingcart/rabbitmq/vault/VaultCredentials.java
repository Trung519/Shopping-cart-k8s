package com.shoppingcart.rabbitmq.vault;

import java.time.Duration;
import java.time.Instant;

/**
 * Represents credentials obtained from Vault for RabbitMQ authentication.
 *
 * @param username  The RabbitMQ username
 * @param password  The RabbitMQ password
 * @param ttl       The time-to-live for these credentials
 * @param leaseId   The Vault lease ID for renewal/revocation
 * @param expiresAt The expiration timestamp
 */
public record VaultCredentials(
        String username,
        String password,
        Duration ttl,
        String leaseId,
        Instant expiresAt
) {
    /**
     * Creates credentials with calculated expiration time.
     */
    public static VaultCredentials of(String username, String password, Duration ttl, String leaseId) {
        return new VaultCredentials(
                username,
                password,
                ttl,
                leaseId,
                Instant.now().plus(ttl)
        );
    }

    /**
     * Checks if the credentials have expired.
     */
    public boolean isExpired() {
        return Instant.now().isAfter(expiresAt);
    }

    /**
     * Checks if the credentials should be renewed based on the threshold.
     *
     * @param renewalThreshold Percentage of TTL at which to renew (0.0 to 1.0)
     */
    public boolean shouldRenew(double renewalThreshold) {
        var now = Instant.now();
        var renewalPoint = expiresAt.minus(ttl.multipliedBy((long) ((1 - renewalThreshold) * 100)).dividedBy(100));
        return now.isAfter(renewalPoint);
    }

    /**
     * Returns the remaining time until expiration.
     */
    public Duration remainingTime() {
        var remaining = Duration.between(Instant.now(), expiresAt);
        return remaining.isNegative() ? Duration.ZERO : remaining;
    }

    @Override
    public String toString() {
        return String.format("VaultCredentials{username='%s', ttl=%s, expiresAt=%s, leaseId='%s'}",
                username, ttl, expiresAt, leaseId);
    }
}
