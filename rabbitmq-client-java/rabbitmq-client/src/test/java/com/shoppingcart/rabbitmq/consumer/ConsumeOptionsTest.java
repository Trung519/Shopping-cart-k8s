package com.shoppingcart.rabbitmq.consumer;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConsumeOptionsTest {

    @Test
    void of_shouldCreateWithQueueName() {
        var options = ConsumeOptions.of("my-queue");

        assertEquals("my-queue", options.getQueue());
    }

    @Test
    void defaults_shouldHaveCorrectValues() {
        var options = ConsumeOptions.of("my-queue");

        assertFalse(options.isAutoAck());
        assertFalse(options.isExclusive());
        assertEquals(10, options.getPrefetchCount());
        assertTrue(options.isRequeueOnFailure());
        assertEquals(3, options.getMaxRetries());
        assertNotNull(options.getArguments());
        assertNotNull(options.getQueueOptions());
    }

    @Test
    void builder_shouldSetAllFields() {
        var options = ConsumeOptions.builder()
                .queue("my-queue")
                .consumerTag("consumer-1")
                .autoAck(true)
                .exclusive(true)
                .prefetchCount(50)
                .requeueOnFailure(false)
                .maxRetries(5)
                .build();

        assertEquals("my-queue", options.getQueue());
        assertEquals("consumer-1", options.getConsumerTag());
        assertTrue(options.isAutoAck());
        assertTrue(options.isExclusive());
        assertEquals(50, options.getPrefetchCount());
        assertFalse(options.isRequeueOnFailure());
        assertEquals(5, options.getMaxRetries());
    }

    @Test
    void queueOptions_shouldHaveDefaults() {
        var queueOptions = ConsumeOptions.QueueOptions.defaults();

        assertTrue(queueOptions.isDurable());
        assertFalse(queueOptions.isExclusive());
        assertFalse(queueOptions.isAutoDelete());
        assertNotNull(queueOptions.getArguments());
    }

    @Test
    void queueOptions_shouldBeConfigurable() {
        var queueOptions = ConsumeOptions.QueueOptions.builder()
                .durable(false)
                .exclusive(true)
                .autoDelete(true)
                .build();

        assertFalse(queueOptions.isDurable());
        assertTrue(queueOptions.isExclusive());
        assertTrue(queueOptions.isAutoDelete());
    }
}
