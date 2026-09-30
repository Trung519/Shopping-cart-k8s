package com.shoppingcart.rabbitmq.cli;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.consumer.Consumer;
import com.shoppingcart.rabbitmq.consumer.ConsumeOptions;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Command-line consumer tool for receiving messages from RabbitMQ.
 * <p>
 * Usage: java -jar rabbitmq-cli-consumer.jar [options]
 */
@Slf4j
@SpringBootApplication(scanBasePackages = "com.shoppingcart.rabbitmq")
@Command(name = "sc-mq-consumer", mixinStandardHelpOptions = true, version = "1.0.0",
        description = "Consumes messages from RabbitMQ")
public class ConsumerCli implements Callable<Integer> {

    private static final String DEFAULT_EXCHANGE = "cli-events";
    private static final String DEFAULT_QUEUE = "cli-messages";

    private Consumer consumer;
    private Publisher publisher;
    private ObjectMapper objectMapper;

    @Option(names = {"-q", "--queue"}, description = "Queue name", defaultValue = DEFAULT_QUEUE)
    private String queueName;

    @Option(names = {"-e", "--exchange"}, description = "Exchange to bind to", defaultValue = DEFAULT_EXCHANGE)
    private String exchange;

    @Option(names = {"-r", "--routing-key"}, description = "Routing key pattern for binding", defaultValue = "#")
    private String routingKeyPattern;

    @Option(names = {"-n", "--count"}, description = "Number of messages to consume (0 = unlimited)", defaultValue = "0")
    private int count;

    @Option(names = {"--auto-ack"}, description = "Use auto-acknowledgment")
    private boolean autoAck;

    @Option(names = {"--prefetch"}, description = "Prefetch count", defaultValue = "10")
    private int prefetch;

    @Option(names = {"--json"}, description = "Output messages as JSON")
    private boolean jsonOutput;

    @Option(names = {"--quiet"}, description = "Only output message bodies")
    private boolean quiet;

    @Option(names = {"--no-setup"}, description = "Skip exchange/queue setup")
    private boolean noSetup;

    private final CountDownLatch shutdownLatch = new CountDownLatch(1);
    private final AtomicInteger messagesReceived = new AtomicInteger(0);

    public static void main(String[] args) {
        // Start Spring context
        ConfigurableApplicationContext context = SpringApplication.run(ConsumerCli.class, args);

        // Get the CLI instance and inject dependencies
        ConsumerCli cli = new ConsumerCli();
        cli.consumer = context.getBean(Consumer.class);
        cli.publisher = context.getBean(Publisher.class);
        cli.objectMapper = context.getBean(ObjectMapper.class);

        // Run picocli
        int exitCode = new CommandLine(cli).execute(args);

        // Close context and exit
        context.close();
        System.exit(exitCode);
    }

    @Override
    public Integer call() {
        try {
            // Setup infrastructure unless --no-setup
            if (!noSetup) {
                setupInfrastructure();
            }

            // Register shutdown hook
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                if (!quiet) {
                    System.out.println();
                    System.out.println("Shutting down consumer...");
                    System.out.printf("Total messages received: %d%n", messagesReceived.get());
                }
                consumer.stopAll();
                shutdownLatch.countDown();
            }));

            // Build consume options
            ConsumeOptions options = ConsumeOptions.builder()
                    .queue(queueName)
                    .autoAck(autoAck)
                    .prefetchCount(prefetch)
                    .requeueOnFailure(true)
                    .build();

            if (!quiet) {
                System.out.printf("Consuming from queue '%s'... (Ctrl+C to stop)%n", queueName);
            }

            // Start consuming
            consumer.consume(options, message -> {
                int received = messagesReceived.incrementAndGet();
                String body = new String(message.getBody(), StandardCharsets.UTF_8);
                String routingKey = message.getMessageProperties().getReceivedRoutingKey();

                if (jsonOutput) {
                    Map<String, Object> output = Map.of(
                            "count", received,
                            "exchange", message.getMessageProperties().getReceivedExchange() != null
                                    ? message.getMessageProperties().getReceivedExchange() : "",
                            "routingKey", routingKey != null ? routingKey : "",
                            "body", body
                    );
                    System.out.println(objectMapper.writeValueAsString(output));
                } else if (quiet) {
                    System.out.println(body);
                } else {
                    System.out.printf("[#%d] %s%n", received, routingKey != null ? routingKey : "(no routing key)");
                    System.out.println(body);
                    System.out.println();
                }

                // Check if we've received enough messages
                if (count > 0 && received >= count) {
                    if (!quiet) {
                        System.out.printf("Received %d messages, stopping%n", received);
                    }
                    shutdownLatch.countDown();
                }
            });

            // Wait for shutdown
            shutdownLatch.await();

            return 0;

        } catch (Exception e) {
            if (jsonOutput) {
                try {
                    Map<String, Object> result = Map.of(
                            "status", "error",
                            "error", e.getMessage()
                    );
                    System.err.println(objectMapper.writeValueAsString(result));
                } catch (Exception ignored) {
                    System.err.println("{\"status\":\"error\",\"error\":\"" + e.getMessage() + "\"}");
                }
            } else {
                System.err.println("Error: " + e.getMessage());
                if (!quiet) {
                    e.printStackTrace();
                }
            }
            return 1;
        }
    }

    private void setupInfrastructure() {
        if (!quiet) {
            System.out.println("Setting up RabbitMQ infrastructure...");
        }

        // Declare exchange
        publisher.declareExchange(exchange, Publisher.ExchangeType.TOPIC, true, false);
        if (!quiet) {
            System.out.printf("  Declared exchange: %s%n", exchange);
        }

        // Declare queue
        consumer.declareQueue(queueName, ConsumeOptions.QueueOptions.defaults());
        if (!quiet) {
            System.out.printf("  Declared queue: %s%n", queueName);
        }

        // Bind queue to exchange
        consumer.bindQueue(queueName, exchange, routingKeyPattern);
        if (!quiet) {
            System.out.printf("  Bound queue to exchange with pattern: %s%n", routingKeyPattern);
            System.out.println();
        }
    }
}
