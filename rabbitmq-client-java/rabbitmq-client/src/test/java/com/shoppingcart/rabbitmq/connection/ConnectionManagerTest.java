package com.shoppingcart.rabbitmq.connection;

import com.shoppingcart.rabbitmq.config.RabbitMQProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ConnectionManagerTest {

    @Mock
    private CachingConnectionFactory mockFactory;

    @Test
    void getStats_returnsZeroStats_whenCachePropertiesThrowsNpe() {
        when(mockFactory.getCacheProperties()).thenThrow(new NullPointerException("no channel opened yet"));

        var manager = new ConnectionManager(new RabbitMQProperties());
        ReflectionTestUtils.setField(manager, "connectionFactory", mockFactory);

        var stats = assertDoesNotThrow(manager::getStats);

        assertEquals(0, stats.totalChannels());
        assertEquals(0, stats.activeChannels());
        assertEquals(0, stats.idleChannels());
    }
}
