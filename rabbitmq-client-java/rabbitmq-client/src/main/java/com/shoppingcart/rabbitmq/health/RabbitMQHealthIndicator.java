package com.shoppingcart.rabbitmq.health;

import com.shoppingcart.rabbitmq.connection.ConnectionManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;

/**
 * Spring Boot Actuator health indicator for RabbitMQ connection.
 */
@Slf4j
@RequiredArgsConstructor
public class RabbitMQHealthIndicator implements HealthIndicator {

    private final ConnectionManager connectionManager;

    @Override
    public Health health() {
        try {
            if (connectionManager.isHealthy()) {
                var stats = connectionManager.getStats();
                return Health.up()
                        .withDetail("status", "Connected")
                        .withDetail("totalChannels", stats.totalChannels())
                        .withDetail("activeChannels", stats.activeChannels())
                        .withDetail("idleChannels", stats.idleChannels())
                        .build();
            } else {
                return Health.down()
                        .withDetail("status", "Disconnected")
                        .withDetail("error", "Connection is not healthy")
                        .build();
            }
        } catch (Exception e) {
            log.warn("Health check failed", e);
            return Health.down()
                    .withDetail("status", "Error")
                    .withDetail("error", e.getMessage())
                    .build();
        }
    }
}
