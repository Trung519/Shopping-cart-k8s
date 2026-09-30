package com.shoppingcart.rabbitmq.examples;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.consumer.Consumer;
import com.shoppingcart.rabbitmq.consumer.ConsumeOptions;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import com.shoppingcart.rabbitmq.publisher.PublishOptions;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Combined demo that runs both publisher and consumer together.
 *
 * This is the recommended way to test the library - single command:
 *   make demo
 *
 * Flow:
 *   1. Set up exchange and queue
 *   2. Start consumer
 *   3. Publish messages
 *   4. Wait for all messages to be received
 *   5. Clean shutdown
 */
@Slf4j
@SpringBootApplication(scanBasePackages = "com.shoppingcart.rabbitmq")
@RequiredArgsConstructor
public class DemoExample implements CommandLineRunner {

    private static final String EXCHANGE = "demo-events";
    private static final String QUEUE = "demo-order-events";
    private static final String ROUTING_KEY_PATTERN = "order.#";
    private static final int MESSAGE_COUNT = 8;

    private final Publisher publisher;
    private final Consumer consumer;
    private final ObjectMapper objectMapper;

    public static void main(String[] args) {
        SpringApplication.run(DemoExample.class, args);
    }

    @Override
    public void run(String... args) throws Exception {
        printHeader();

        // Step 1: Set up infrastructure
        log.info("Step 1: Setting up RabbitMQ infrastructure...");
        setupInfrastructure();
        log.info("  Exchange: {} (topic, durable)", EXCHANGE);
        log.info("  Queue: {} (durable)", QUEUE);
        log.info("  Binding: {}", ROUTING_KEY_PATTERN);

        // Step 2: Start consumer
        log.info("");
        log.info("Step 2: Starting consumer...");

        AtomicInteger receivedCount = new AtomicInteger(0);
        CountDownLatch allReceived = new CountDownLatch(MESSAGE_COUNT);

        String consumerId = startConsumer(receivedCount, allReceived);
        log.info("  Consumer started with ID: {}", consumerId);

        // Give consumer time to initialize
        Thread.sleep(500);

        // Step 3: Publish messages
        log.info("");
        log.info("Step 3: Publishing {} messages...", MESSAGE_COUNT);
        printSeparator();

        publishMessages();

        printSeparator();
        log.info("  All messages published!");

        // Step 4: Wait for messages to be received
        log.info("");
        log.info("Step 4: Waiting for messages to be received...");

        boolean allReceived_ = allReceived.await(10, TimeUnit.SECONDS);

        if (allReceived_) {
            log.info("  All {} messages received!", MESSAGE_COUNT);
        } else {
            log.warn("  Timeout! Only received {}/{} messages", receivedCount.get(), MESSAGE_COUNT);
        }

        // Step 5: Clean shutdown
        log.info("");
        log.info("Step 5: Shutting down...");
        consumer.stop(consumerId);
        log.info("  Consumer stopped");

        printFooter(receivedCount.get());

        System.exit(0);
    }

    private void setupInfrastructure() {
        publisher.declareExchange(EXCHANGE, Publisher.ExchangeType.TOPIC, true, false);
        consumer.declareQueue(QUEUE, ConsumeOptions.QueueOptions.defaults());
        consumer.bindQueue(QUEUE, EXCHANGE, ROUTING_KEY_PATTERN);
    }

    private String startConsumer(AtomicInteger receivedCount, CountDownLatch latch) {
        ConsumeOptions options = ConsumeOptions.builder()
                .queue(QUEUE)
                .autoAck(false)
                .prefetchCount(10)
                .build();

        return consumer.consume(options, message -> {
            String body = new String(message.getBody(), StandardCharsets.UTF_8);
            String routingKey = message.getMessageProperties().getReceivedRoutingKey();
            int count = receivedCount.incrementAndGet();

            log.info("  [Received #{}] {} -> {}", count, routingKey, body);
            latch.countDown();
        });
    }

    private void publishMessages() throws Exception {
        // 1. Order created
        publish("order.created", Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "customerId", "CUST-001",
                "amount", 99.99,
                "timestamp", Instant.now().toString()
        ));

        // 2. Order updated
        publish("order.updated", Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "status", "PROCESSING",
                "timestamp", Instant.now().toString()
        ));

        // 3. Order shipped
        publish("order.shipped", Map.of(
                "orderId", "ORD-" + System.currentTimeMillis(),
                "status", "SHIPPED",
                "trackingNumber", "TRK-123456",
                "timestamp", Instant.now().toString()
        ));

        // 4-8. Batch of item events
        for (int i = 1; i <= 5; i++) {
            publish("order.item.added", Map.of(
                    "orderId", "ORD-BATCH",
                    "itemId", "ITEM-" + i,
                    "productName", "Product " + i,
                    "quantity", i,
                    "price", 10.0 * i
            ));
            Thread.sleep(100);
        }
    }

    private void publish(String routingKey, Map<String, Object> data) throws Exception {
        publisher.publish(EXCHANGE, routingKey, data);
        log.info("  [Published] {} -> {}", routingKey, objectMapper.writeValueAsString(data));
    }

    private void printHeader() {
        log.info("");
        log.info("============================================================");
        log.info("  RabbitMQ Client Java - Demo");
        log.info("============================================================");
        log.info("");
        log.info("This demo will:");
        log.info("  1. Set up exchange and queue");
        log.info("  2. Start a consumer");
        log.info("  3. Publish {} messages", MESSAGE_COUNT);
        log.info("  4. Wait for all messages to be received");
        log.info("  5. Clean shutdown");
        log.info("");
    }

    private void printSeparator() {
        log.info("------------------------------------------------------------");
    }

    private void printFooter(int received) {
        log.info("");
        log.info("============================================================");
        log.info("  Demo Complete!");
        log.info("  Messages published: {}", MESSAGE_COUNT);
        log.info("  Messages received:  {}", received);
        log.info("============================================================");
    }
}
