package com.shoppingcart.rabbitmq.vault;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.*;

class VaultCredentialsTest {

    @Test
    void of_shouldCreateCredentialsWithExpirationTime() {
        var credentials = VaultCredentials.of("user", "pass", Duration.ofHours(1), "lease-123");

        assertEquals("user", credentials.username());
        assertEquals("pass", credentials.password());
        assertEquals(Duration.ofHours(1), credentials.ttl());
        assertEquals("lease-123", credentials.leaseId());
        assertNotNull(credentials.expiresAt());
    }

    @Test
    void isExpired_shouldReturnFalseForFreshCredentials() {
        var credentials = VaultCredentials.of("user", "pass", Duration.ofHours(1), "lease-123");

        assertFalse(credentials.isExpired());
    }

    @Test
    void isExpired_shouldReturnTrueForExpiredCredentials() {
        var credentials = new VaultCredentials(
                "user", "pass",
                Duration.ofHours(1),
                "lease-123",
                Instant.now().minusSeconds(60)
        );

        assertTrue(credentials.isExpired());
    }

    @Test
    void shouldRenew_shouldReturnFalseWhenFresh() {
        var credentials = VaultCredentials.of("user", "pass", Duration.ofHours(1), "lease-123");

        // With 80% threshold, should not renew when mostly fresh
        assertFalse(credentials.shouldRenew(0.8));
    }

    @Test
    void shouldRenew_shouldReturnTrueWhenNearExpiry() {
        // Create credentials that expire in 5 minutes with 1 hour TTL
        var credentials = new VaultCredentials(
                "user", "pass",
                Duration.ofHours(1),
                "lease-123",
                Instant.now().plus(Duration.ofMinutes(5))
        );

        // With 80% threshold (12 minutes remaining), should renew
        assertTrue(credentials.shouldRenew(0.8));
    }

    @Test
    void remainingTime_shouldReturnPositiveDuration() {
        var credentials = VaultCredentials.of("user", "pass", Duration.ofHours(1), "lease-123");

        var remaining = credentials.remainingTime();
        assertTrue(remaining.toMinutes() > 50);
    }

    @Test
    void remainingTime_shouldReturnZeroForExpired() {
        var credentials = new VaultCredentials(
                "user", "pass",
                Duration.ofHours(1),
                "lease-123",
                Instant.now().minusSeconds(60)
        );

        assertEquals(Duration.ZERO, credentials.remainingTime());
    }

    @Test
    void toString_shouldNotExposePassword() {
        var credentials = VaultCredentials.of("user", "secret-password", Duration.ofHours(1), "lease-123");

        var str = credentials.toString();
        assertTrue(str.contains("user"));
        assertFalse(str.contains("secret-password"));
    }
}
