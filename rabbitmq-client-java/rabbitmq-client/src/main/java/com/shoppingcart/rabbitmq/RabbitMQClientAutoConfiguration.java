package com.shoppingcart.rabbitmq;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.circuitbreaker.CircuitBreakerConfig;
import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import com.shoppingcart.rabbitmq.connection.ConnectionManager;
import com.shoppingcart.rabbitmq.consumer.Consumer;
import com.shoppingcart.rabbitmq.dlq.DLQManager;
import com.shoppingcart.rabbitmq.health.RabbitMQHealthIndicator;
import com.shoppingcart.rabbitmq.health.VaultHealthIndicator;
import com.shoppingcart.rabbitmq.metrics.RabbitMQMetrics;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import com.shoppingcart.rabbitmq.retry.RetryConfig;
import com.shoppingcart.rabbitmq.vault.VaultCredentialManager;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.vault.core.VaultTemplate;

/**
 * Auto-configuration for the RabbitMQ client library.
 * <p>
 * Automatically configures all components when Spring Boot starts.
 */
@AutoConfiguration
@EnableConfigurationProperties(RabbitMQProperties.class)
@EnableScheduling
public class RabbitMQClientAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public ObjectMapper objectMapper() {
        return new ObjectMapper();
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(VaultTemplate.class)
    @ConditionalOnProperty(name = "rabbitmq.vault.enabled", havingValue = "true", matchIfMissing = true)
    public VaultCredentialManager vaultCredentialManager(VaultTemplate vaultTemplate,
                                                          RabbitMQProperties properties) {
        return new VaultCredentialManager(vaultTemplate, properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(VaultCredentialManager.class)
    public ConnectionManager connectionManagerWithVault(RabbitMQProperties properties,
                                                         VaultCredentialManager vaultCredentialManager) {
        return new ConnectionManager(properties, vaultCredentialManager);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(name = "rabbitmq.vault.enabled", havingValue = "false")
    public ConnectionManager connectionManagerWithoutVault(RabbitMQProperties properties) {
        return new ConnectionManager(properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(MeterRegistry.class)
    public RabbitMQMetrics rabbitMQMetrics(MeterRegistry meterRegistry) {
        return new RabbitMQMetrics(meterRegistry);
    }

    @Bean
    @ConditionalOnMissingBean
    public RabbitMQMetrics noOpRabbitMQMetrics() {
        // Create a no-op metrics instance with SimpleMeterRegistry when no registry is configured
        return new RabbitMQMetrics(new io.micrometer.core.instrument.simple.SimpleMeterRegistry());
    }

    @Bean
    @ConditionalOnMissingBean
    public RetryConfig retryConfig(RabbitMQProperties properties) {
        return new RetryConfig(properties);
    }

    @Bean
    @ConditionalOnMissingBean
    public CircuitBreakerConfig circuitBreakerConfig(RabbitMQProperties properties) {
        return new CircuitBreakerConfig(properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(ConnectionManager.class)
    public Publisher publisher(ConnectionManager connectionManager,
                               ObjectMapper objectMapper,
                               RabbitMQMetrics metrics,
                               RabbitMQProperties properties) {
        return new Publisher(connectionManager, objectMapper, metrics, properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean(ConnectionManager.class)
    public Consumer consumer(ConnectionManager connectionManager,
                             RabbitMQMetrics metrics,
                             RabbitMQProperties properties) {
        return new Consumer(connectionManager, metrics, properties);
    }

    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnBean({ConnectionManager.class, Publisher.class})
    public DLQManager dlqManager(ConnectionManager connectionManager, Publisher publisher) {
        return new DLQManager(connectionManager, publisher);
    }

    @Bean
    @ConditionalOnMissingBean(name = "rabbitMQHealthIndicator")
    @ConditionalOnBean(ConnectionManager.class)
    @ConditionalOnClass(HealthIndicator.class)
    public HealthIndicator rabbitMQHealthIndicator(ConnectionManager connectionManager) {
        return new RabbitMQHealthIndicator(connectionManager);
    }

    @Bean
    @ConditionalOnMissingBean(name = "vaultHealthIndicator")
    @ConditionalOnBean(VaultCredentialManager.class)
    @ConditionalOnClass(HealthIndicator.class)
    public HealthIndicator vaultHealthIndicator(VaultCredentialManager vaultCredentialManager) {
        return new VaultHealthIndicator(vaultCredentialManager);
    }
}
