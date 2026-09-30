package com.shoppingcart.rabbitmq.examples;

import com.shoppingcart.rabbitmq.publisher.Publisher;
import com.shoppingcart.rabbitmq.publisher.PublishOptions;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.time.Instant;
import java.util.Map;

/**
 * Example application demonstrating message publishing.
 *
 * Usage:
 *   1. First start the consumer: make run-consumer
 *   2. Then run this publisher: make run-publisher
 *   3. Watch messages appear in the consumer terminal
 */
@Slf4j
@SpringBootApplication(scanBasePackages = "com.shoppingcart.rabbitmq")
@RequiredArgsConstructor
public class PublisherExample implements CommandLineRunner {

    private static final String EXCHANGE = "demo-events";

    private final Publisher publisher;

    public static void main(String[] args) {
        SpringApplication.run(PublisherExample.class, args);
    }

    @Override
    public void run(String... args) throws Exception {
        log.info("=".repeat(60));
        log.info("RabbitMQ Publisher Example");
        log.info("=".repeat(60));

        // Declare exchange
        log.info("Declaring exchange: {}", EXCHANGE);
        publisher.declareExchange(EXCHANGE, Publisher.ExchangeType.TOPIC, true, false);

        log.info("-".repeat(60));
        log.info("Publishing messages to exchange: {}", EXCHANGE);
        log.info("-".repeat(60));

        // 1. Publish order.created event
        Map<String, Object> orderCreated = Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "customerId", "CUST-001",
                "amount", 99.99,
                "timestamp", Instant.now().toString()
        );
        publisher.publish(EXCHANGE, "order.created", orderCreated);
        log.info("Published: order.created -> {}", orderCreated);

        // 2. Publish order.updated event with custom options
        Map<String, Object> orderUpdated = Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "status", "PROCESSING",
                "timestamp", Instant.now().toString()
        );
        PublishOptions options = PublishOptions.builder()
                .exchange(EXCHANGE)
                .routingKey("order.updated")
                .priority(5)
                .build()
                .withHeader("source", "publisher-example");
        publisher.publish(options, orderUpdated);
        log.info("Published: order.updated -> {}", orderUpdated);

        // 3. Publish order.shipped event
        Map<String, Object> orderShipped = Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "status", "SHIPPED",
                "trackingNumber", "TRK-123456",
                "timestamp", Instant.now().toString()
        );
        publisher.publish(EXCHANGE, "order.shipped", orderShipped);
        log.info("Published: order.shipped -> {}", orderShipped);

        // 4. Publish batch of order.item events
        log.info("-".repeat(60));
        log.info("Publishing batch of {} item events...", 5);
        for (int i = 1; i <= 5; i++) {
            Map<String, Object> itemEvent = Map.of(
                    "orderId", "ORD-BATCH",
                    "itemId", "ITEM-" + i,
                    "productName", "Product " + i,
                    "quantity", i,
                    "price", 10.0 * i
            );
            publisher.publish(EXCHANGE, "order.item.added", itemEvent);
            log.info("Published: order.item.added #{} -> {}", i, itemEvent);
            Thread.sleep(200); // Small delay between messages
        }

        log.info("-".repeat(60));
        log.info("All messages published successfully!");
        log.info("Total: 8 messages sent to exchange '{}'", EXCHANGE);
        log.info("-".repeat(60));

        // Give time for messages to be delivered before exit
        Thread.sleep(500);

        log.info("Publisher example completed");
        System.exit(0);
    }
}
