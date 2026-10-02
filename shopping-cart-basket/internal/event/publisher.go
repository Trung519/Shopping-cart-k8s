package event

import (
	"context"
	"encoding/json"
	"fmt"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
	"net/url"
	"sync"
	"time"

	"github.com/rabbitmq/amqp091-go"
	"github.com/user/shopping-cart-basket/internal/model"
	"go.uber.org/zap"
)

// Publisher publishes cart events to RabbitMQ
type Publisher struct {
	exchange   string
	logger     *zap.Logger
	connection *amqp091.Connection
	channel    *amqp091.Channel
	mu         sync.Mutex
}

// NewPublisher connects to RabbitMQ and declares the topic exchange used for cart events.
func NewPublisher(exchange, host, port, vhost, username, password string, useTLS bool, logger *zap.Logger) (*Publisher, error) {
	if useTLS {
		return nil, fmt.Errorf("RabbitMQ TLS is not configured for basket-service")
	}

	uri := (&url.URL{
		Scheme: "amqp",
		User:   url.UserPassword(username, password),
		Host:   host + ":" + port,
		Path:   vhost,
	}).String()
	connection, err := amqp091.DialConfig(uri, amqp091.Config{Heartbeat: 10 * time.Second})
	if err != nil {
		return nil, fmt.Errorf("connect to RabbitMQ: %w", err)
	}

	channel, err := connection.Channel()
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("open RabbitMQ channel: %w", err)
	}
	if err := channel.ExchangeDeclare(exchange, "topic", true, false, false, false, nil); err != nil {
		_ = channel.Close()
		_ = connection.Close()
		return nil, fmt.Errorf("declare RabbitMQ exchange %q: %w", exchange, err)
	}

	return &Publisher{exchange: exchange, logger: logger, connection: connection, channel: channel}, nil
}

// Publish publishes an event to RabbitMQ
func (p *Publisher) Publish(ctx context.Context, event *model.EventEnvelope) error {
	ctx, span := otel.Tracer("shopping/amqp").Start(ctx, event.Type+" publish", trace.WithSpanKind(trace.SpanKindProducer), trace.WithAttributes(attribute.String("messaging.system", "rabbitmq"), attribute.String("messaging.destination.name", p.exchange), attribute.String("messaging.rabbitmq.destination.routing_key", event.Type)))
	defer span.End()
	carrier := propagation.MapCarrier{}
	otel.GetTextMapPropagator().Inject(ctx, carrier)
	headers := amqp091.Table{}
	for key, value := range carrier {
		headers[key] = value
	}
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	p.mu.Lock()
	defer p.mu.Unlock()
	if p.channel == nil || p.channel.IsClosed() || p.connection == nil || p.connection.IsClosed() {
		return fmt.Errorf("RabbitMQ publisher is not connected")
	}

	if err := p.channel.PublishWithContext(ctx, p.exchange, event.Type, true, false, amqp091.Publishing{
		ContentType:  "application/json",
		Headers:      headers,
		DeliveryMode: amqp091.Persistent,
		MessageId:    event.ID,
		Timestamp:    time.Now().UTC(),
		Body:         data,
	}); err != nil {
		span.SetStatus(codes.Error, "RabbitMQ publish failed")
		return fmt.Errorf("publish event %q: %w", event.Type, err)
	}

	p.logger.Info("published event to RabbitMQ",
		zap.String("trace_id", span.SpanContext().TraceID().String()),
		zap.String("span_id", span.SpanContext().SpanID().String()),
		zap.String("eventType", event.Type),
		zap.String("eventId", event.ID),
		zap.String("correlationId", event.CorrelationID),
		zap.String("exchange", p.exchange),
		zap.String("routingKey", event.Type),
		zap.Int("size", len(data)),
	)

	return nil
}

// Close closes the publisher
func (p *Publisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()
	var closeErr error
	if p.channel != nil && !p.channel.IsClosed() {
		closeErr = p.channel.Close()
	}
	if p.connection != nil && !p.connection.IsClosed() {
		if err := p.connection.Close(); err != nil && closeErr == nil {
			closeErr = err
		}
	}
	return closeErr
}

// NoopPublisher is a publisher that does nothing (for testing)
type NoopPublisher struct{}

// NewNoopPublisher creates a new no-op publisher
func NewNoopPublisher() *NoopPublisher {
	return &NoopPublisher{}
}

// Publish does nothing
func (p *NoopPublisher) Publish(ctx context.Context, event *model.EventEnvelope) error {
	return nil
}
