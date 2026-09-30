package com.shoppingcart.rabbitmq.publisher;

import com.shoppingcart.rabbitmq.exception.PublishException;
import lombok.extern.slf4j.Slf4j;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Batch publisher for sending multiple messages efficiently.
 * <p>
 * Collects messages and publishes them in batches for improved throughput.
 */
@Slf4j
public class BatchPublisher {

    private final Publisher publisher;
    private final int batchSize;
    private final List<BatchMessage> pending;
    private final ExecutorService executor;

    public BatchPublisher(Publisher publisher, int batchSize) {
        this.publisher = publisher;
        this.batchSize = batchSize;
        this.pending = new ArrayList<>();
        this.executor = Executors.newVirtualThreadPerTaskExecutor();
    }

    /**
     * Adds a message to the batch.
     *
     * @param options The publish options
     * @param body    The message body
     */
    public synchronized void add(PublishOptions options, Object body) {
        pending.add(new BatchMessage(options, body));

        if (pending.size() >= batchSize) {
            flush();
        }
    }

    /**
     * Adds a message to the batch with default options.
     */
    public void add(String exchange, String routingKey, Object body) {
        add(PublishOptions.of(exchange, routingKey), body);
    }

    /**
     * Flushes all pending messages.
     *
     * @return Number of messages published
     */
    public synchronized int flush() {
        if (pending.isEmpty()) {
            return 0;
        }

        List<BatchMessage> toPublish = new ArrayList<>(pending);
        pending.clear();

        log.debug("Flushing batch of {} messages", toPublish.size());

        int successCount = 0;
        List<PublishException> errors = new ArrayList<>();

        for (BatchMessage msg : toPublish) {
            try {
                publisher.publish(msg.options(), msg.body());
                successCount++;
            } catch (PublishException e) {
                errors.add(e);
                log.warn("Failed to publish message in batch: {}", e.getMessage());
            }
        }

        if (!errors.isEmpty()) {
            log.warn("Batch publish completed with {} successes and {} failures",
                    successCount, errors.size());
        } else {
            log.debug("Batch publish completed successfully: {} messages", successCount);
        }

        return successCount;
    }

    /**
     * Flushes all pending messages asynchronously.
     *
     * @return CompletableFuture with the number of messages published
     */
    public CompletableFuture<Integer> flushAsync() {
        return CompletableFuture.supplyAsync(this::flush, executor);
    }

    /**
     * Gets the number of pending messages.
     */
    public synchronized int pendingCount() {
        return pending.size();
    }

    /**
     * Clears all pending messages without publishing.
     */
    public synchronized void clear() {
        pending.clear();
    }

    /**
     * Closes the batch publisher, flushing any pending messages.
     */
    public void close() {
        flush();
        executor.shutdown();
    }

    /**
     * Record holding a message to be published.
     */
    private record BatchMessage(PublishOptions options, Object body) {}
}
