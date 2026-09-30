package com.shoppingcart.rabbitmq.health;

import com.shoppingcart.rabbitmq.vault.VaultCredentialManager;
import com.shoppingcart.rabbitmq.vault.VaultCredentials;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;

import java.time.Duration;

/**
 * Spring Boot Actuator health indicator for Vault credential status.
 */
@Slf4j
@RequiredArgsConstructor
public class VaultHealthIndicator implements HealthIndicator {

    private final VaultCredentialManager credentialManager;

    @Override
    public Health health() {
        try {
            if (!credentialManager.hasValidCredentials()) {
                return Health.down()
                        .withDetail("status", "No valid credentials")
                        .withDetail("error", "Credentials are missing or expired")
                        .build();
            }

            VaultCredentials credentials = credentialManager.getCredentials();
            Duration remaining = credentials.remainingTime();

            // Warning if less than 10 minutes remaining
            if (remaining.toMinutes() < 10) {
                return Health.status("WARNING")
                        .withDetail("status", "Credentials expiring soon")
                        .withDetail("username", credentials.username())
                        .withDetail("remainingTime", remaining.toString())
                        .withDetail("expiresAt", credentials.expiresAt().toString())
                        .build();
            }

            return Health.up()
                    .withDetail("status", "Valid credentials")
                    .withDetail("username", credentials.username())
                    .withDetail("remainingTime", remaining.toString())
                    .withDetail("expiresAt", credentials.expiresAt().toString())
                    .build();

        } catch (Exception e) {
            log.warn("Vault health check failed", e);
            return Health.down()
                    .withDetail("status", "Error")
                    .withDetail("error", e.getMessage())
                    .build();
        }
    }
}
