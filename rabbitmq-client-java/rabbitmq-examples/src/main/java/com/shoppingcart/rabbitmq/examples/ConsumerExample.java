package com.shoppingcart.rabbitmq.examples;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.consumer.Consumer;
import com.shoppingcart.rabbitmq.consumer.ConsumeOptions;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Example application demonstrating message consumption.
 *
 * Usage:
 *   1. Start this consumer first: make run-consumer
 *   2. In another terminal, run the publisher: make run-publisher
 *   3. Watch messages being received here
 *   4. Press Ctrl+C to stop
 */
@Slf4j
@SpringBootApplication(scanBasePackages = "com.shoppingcart.rabbitmq")
@RequiredArgsConstructor
public class ConsumerExample implements CommandLineRunner {

    private static final String EXCHANGE = "demo-events";
    private static final String QUEUE = "demo-order-events";
    private static final String ROUTING_KEY_PATTERN = "order.#";

    private final Consumer consumer;
    private final Publisher publisher;
    private final ObjectMapper objectMapper;

    public static void main(String[] args) {
        SpringApplication.run(ConsumerExample.class, args);
    }

    @Override
    public void run(String... args) throws Exception {
        log.info("=".repeat(60));
        log.info("RabbitMQ Consumer Example");
        log.info("=".repeat(60));

        // Declare exchange (same as publisher to ensure it exists)
        log.info("Declaring exchange: {}", EXCHANGE);
        publisher.declareExchange(EXCHANGE, Publisher.ExchangeType.TOPIC, true, false);

        // Declare and bind queue
        log.info("Declaring queue: {}", QUEUE);
        consumer.declareQueue(QUEUE, ConsumeOptions.QueueOptions.defaults());

        log.info("Binding queue '{}' to exchange '{}' with pattern '{}'", QUEUE, EXCHANGE, ROUTING_KEY_PATTERN);
        consumer.bindQueue(QUEUE, EXCHANGE, ROUTING_KEY_PATTERN);

        AtomicInteger messageCount = new AtomicInteger(0);

        // Start consuming with manual ack
        ConsumeOptions options = ConsumeOptions.builder()
                .queue(QUEUE)
                .autoAck(false)
                .prefetchCount(10)
                .requeueOnFailure(true)
                .build();

        String consumerId = consumer.consume(options, message -> {
            String body = new String(message.getBody(), StandardCharsets.UTF_8);
            Map<String, Object> data = objectMapper.readValue(body, Map.class);
            int count = messageCount.incrementAndGet();

            log.info("[Message #{}] routingKey={}, data={}",
                    count,
                    message.getMessageProperties().getReceivedRoutingKey(),
                    data);
        });

        log.info("-".repeat(60));
        log.info("Consumer started successfully!");
        log.info("Consumer ID: {}", consumerId);
        log.info("Listening on queue: {}", QUEUE);
        log.info("-".repeat(60));
        log.info("Waiting for messages... (Press Ctrl+C to stop)");
        log.info("");
        log.info("To publish messages, run in another terminal:");
        log.info("  make run-publisher");
        log.info("");

        // Add shutdown hook for graceful shutdown
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            log.info("");
            log.info("-".repeat(60));
            log.info("Shutting down consumer...");
            consumer.stop(consumerId);
            log.info("Total messages received: {}", messageCount.get());
            log.info("Consumer stopped gracefully");
            log.info("-".repeat(60));
        }));

        // Keep running until interrupted
        Thread.currentThread().join();
    }
}
