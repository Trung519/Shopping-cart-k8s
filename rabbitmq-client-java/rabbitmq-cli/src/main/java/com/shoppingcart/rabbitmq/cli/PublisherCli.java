package com.shoppingcart.rabbitmq.cli;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.shoppingcart.rabbitmq.publisher.Publisher;
import com.shoppingcart.rabbitmq.publisher.PublishOptions;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;
import picocli.CommandLine.Parameters;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Callable;

/**
 * Command-line publisher tool for sending messages to RabbitMQ.
 * <p>
 * Usage: java -jar rabbitmq-cli-publisher.jar [options] <event-type> <json-payload>
 */
@Slf4j
@SpringBootApplication(scanBasePackages = "com.shoppingcart.rabbitmq")
@Command(name = "sc-mq-publisher", mixinStandardHelpOptions = true, version = "1.0.0",
        description = "Publishes messages to RabbitMQ")
public class PublisherCli implements Callable<Integer> {

    private Publisher publisher;
    private ObjectMapper objectMapper;

    @Parameters(index = "0", description = "Event type (used as routing key)", defaultValue = "test.event")
    private String eventType;

    @Parameters(index = "1", description = "JSON payload", defaultValue = "{\"message\":\"hello\"}")
    private String payload;

    @Option(names = {"-e", "--exchange"}, description = "Exchange name", defaultValue = "cli-events")
    private String exchange;

    @Option(names = {"-r", "--routing-key"}, description = "Custom routing key (overrides event-type)")
    private String routingKey;

    @Option(names = {"-H", "--header"}, description = "Custom headers (key=value)")
    private Map<String, String> headers = new HashMap<>();

    @Option(names = {"--no-confirm"}, description = "Don't wait for publisher confirms")
    private boolean noConfirm;

    @Option(names = {"--json"}, description = "Output result as JSON")
    private boolean jsonOutput;

    @Option(names = {"--quiet"}, description = "Minimal output")
    private boolean quiet;

    public static void main(String[] args) {
        // Start Spring context
        ConfigurableApplicationContext context = SpringApplication.run(PublisherCli.class, args);

        // Get the CLI instance and inject dependencies
        PublisherCli cli = new PublisherCli();
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
            // Declare exchange
            publisher.declareExchange(exchange, Publisher.ExchangeType.TOPIC, true, false);

            // Use custom routing key or event type
            String rk = routingKey != null ? routingKey : eventType;

            // Build publish options
            PublishOptions options = PublishOptions.builder()
                    .exchange(exchange)
                    .routingKey(rk)
                    .waitForConfirm(!noConfirm)
                    .headers(new HashMap<>(headers))
                    .build();

            // Parse and publish
            Object body;
            try {
                body = objectMapper.readValue(payload, Object.class);
            } catch (Exception e) {
                // Use raw string if not valid JSON
                body = payload;
            }

            publisher.publish(options, body);

            // Output result
            if (jsonOutput) {
                Map<String, Object> result = Map.of(
                        "status", "success",
                        "exchange", exchange,
                        "routingKey", rk
                );
                System.out.println(objectMapper.writeValueAsString(result));
            } else if (!quiet) {
                System.out.printf("Published to exchange='%s', routingKey='%s'%n", exchange, rk);
            }

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
}
