# RabbitMQ Client Library Design

## Overview

This document describes the architecture and design decisions for the shared RabbitMQ client library that will be used across all shopping cart microservices.

**Target Services**: Product Catalog (Python), Cart (Go), Order (Java), Frontend (React/Node.js), Future .NET services

## Implementation Status

### Python Library ✅ COMPLETE

**Repository**: `rabbitmq-client-library/python/`
**Status**: Phase 1 & 2 Complete - Production Ready

**Implemented Features:**
- ✅ Configuration management with validation (`config.py`)
- ✅ Connection management with Vault credential integration (`connection.py`)
- ✅ Publisher with confirmation support and JSON serialization (`publisher.py`)
- ✅ Consumer with auto/manual acknowledgment (`consumer.py`)
- ✅ Thread-safe connection pooling (`pool.py`)
- ✅ Circuit breaker pattern - CLOSED/OPEN/HALF_OPEN (`circuit_breaker.py`)
- ✅ Retry logic with exponential backoff using tenacity (`retry.py`)
- ✅ Structured logging with structlog - JSON/console output (`logging.py`)
- ✅ Prometheus metrics - publish/consume latency, pool stats, etc. (`metrics.py`)
- ✅ Health checks - liveness, readiness, detailed status (`health.py`)
- ✅ Dead Letter Queue (DLQ) support (`dlq.py`)
- ✅ 233 tests (224 unit + 9 performance benchmarks)

**Performance Benchmarks (measured):**
- Metrics overhead: ~0.02ms per operation
- Pool throughput: ~25,000+ acquire/release cycles/sec
- Publisher overhead: ~28,000 msgs/sec (with JSON serialization)
- Consumer callback: ~46,000 callbacks/sec

### Go Library ✅ COMPLETE

**Repository**: `rabbitmq-client-go/`
**Status**: ✅ COMPLETE - Production Ready

**Implemented Features:**
- ✅ Configuration management with environment variable support (`config.go`)
- ✅ Connection management with Vault credential integration (`connection.go`)
- ✅ Publisher with confirmation support and JSON serialization (`publisher.go`)
- ✅ Consumer with auto/manual acknowledgment (`consumer.go`)
- ✅ Thread-safe connection pooling with channel management (`pool.go`)
- ✅ Circuit breaker pattern using sony/gobreaker (`circuit_breaker.go`)
- ✅ Retry logic with exponential backoff and jitter (`retry.go`)
- ✅ Structured logging with zap - JSON/console output (`logging.go`)
- ✅ Prometheus metrics (`metrics.go`)
- ✅ Health checks (`health.go`)
- ✅ Dead Letter Queue (DLQ) support (`dlq.go`)
- ✅ CLI tools with Kubernetes auto-detection

The Go implementation is in a separate repository for:
- Independent versioning from Python library
- Go module compatibility (`go get github.com/user/rabbitmq-client-go`)
- Native integration with Cart service (Go)

### Java Library ✅ COMPLETE

**Repository**: `rabbitmq-client-java/`
**Status**: ✅ COMPLETE - Production Ready

**Technology Stack:**
- Java 21 (LTS with virtual threads)
- Spring Boot 3.2
- Spring AMQP for RabbitMQ
- Spring Cloud Vault for credentials

**Implemented Features:**
- ✅ Configuration management with `@ConfigurationProperties` (`RabbitMQProperties.java`)
- ✅ Connection management with Vault integration (`ConnectionManager.java`)
- ✅ Static credentials support for non-Vault environments
- ✅ Publisher with confirmation support (`Publisher.java`)
- ✅ Consumer with auto/manual acknowledgment (`Consumer.java`)
- ✅ Batch publishing support (`BatchPublisher.java`)
- ✅ Circuit breaker pattern using Resilience4j (`CircuitBreakerConfig.java`)
- ✅ Retry logic with exponential backoff (`RetryConfig.java`)
- ✅ Micrometer metrics - Prometheus compatible (`RabbitMQMetrics.java`)
- ✅ Health checks - Spring Boot Actuator (`RabbitMQHealthIndicator.java`)
- ✅ Dead Letter Queue (DLQ) support (`DLQManager.java`)
- ✅ CLI tools: `sc-mq-publisher`, `sc-mq-consumer`
- ✅ Spring Boot auto-configuration

**Module Structure:**
- `rabbitmq-client/` - Core library
- `rabbitmq-cli/` - CLI tools
- `rabbitmq-examples/` - Example applications

The Java implementation is in a separate repository for:
- Independent versioning from other libraries
- Maven compatibility
- Native integration with Order service (Java/Spring Boot)
- Spring Boot starter pattern

### .NET Library ✅ COMPLETE

**Repository**: `rabbitmq-client-dotnet/`
**Status**: ✅ COMPLETE - Production Ready

**Technology Stack:**
- .NET 9 (current)
- RabbitMQ.Client (official .NET client)
- VaultSharp for Vault integration
- Polly for resilience patterns
- Microsoft.Extensions.* for DI and configuration

**Implemented Features:**
- ✅ Configuration management with `IOptions<T>` pattern (`RabbitMQOptions.cs`)
- ✅ Connection management with Vault credential integration (`ConnectionManager.cs`)
- ✅ Static credentials support for non-Vault environments
- ✅ Publisher with confirmation support and JSON serialization (`Publisher.cs`)
- ✅ Consumer with auto/manual acknowledgment (`Consumer.cs`)
- ✅ Connection pooling with channel management
- ✅ Circuit breaker pattern using Polly (`CircuitBreakerService.cs`)
- ✅ Retry logic with exponential backoff using Polly (`RetryService.cs`)
- ✅ Structured logging with Serilog
- ✅ Prometheus metrics using prometheus-net (`RabbitMQMetrics.cs`)
- ✅ Health checks - ASP.NET Core Health Checks (`RabbitMQHealthCheck.cs`)
- ✅ Dead Letter Queue (DLQ) support (`DeadLetterQueue.cs`)
- ✅ CLI tools using System.CommandLine (`sc-mq` command)
- ✅ 45 unit tests

**Module Structure:**
```
rabbitmq-client-dotnet/
├── src/
│   ├── ShoppingCart.RabbitMQ/           # Core library
│   │   ├── Configuration/
│   │   ├── Connection/
│   │   ├── Publisher/
│   │   ├── Consumer/
│   │   ├── CircuitBreaker/
│   │   ├── Retry/
│   │   ├── Metrics/
│   │   ├── Health/
│   │   ├── DLQ/
│   │   └── Exceptions/
│   ├── ShoppingCart.RabbitMQ.Cli/       # CLI tools
│   └── ShoppingCart.RabbitMQ.Examples/  # Example demo
├── tests/
│   └── ShoppingCart.RabbitMQ.Tests/
├── ShoppingCart.RabbitMQ.sln
├── CLAUDE.md
└── README.md
```

The .NET implementation is in a separate repository for:
- Independent versioning from other libraries
- NuGet package compatibility
- Follows .NET community conventions
- ASP.NET Core integration pattern

---

## Original Design Document (Go-First Approach)

> **Note**: The following sections document the original Go-first design. While Python was
> implemented first for practical reasons (faster prototyping, existing Product Catalog service),
> the Go library will follow a similar architecture when implemented.

## Language Selection (Original Recommendation)

### Recommendation: Go

**Decision**: Build the core RabbitMQ client library in **Go** with language-specific wrappers for Python and Java.

### Rationale

#### Why Go?

1. **Native RabbitMQ Support**
   - Official AMQP library: `github.com/rabbitmq/amqp091-go`
   - Mature, well-maintained, battle-tested in production
   - Comprehensive documentation and community support
   - Direct access to AMQP protocol features

2. **Performance & Concurrency**
   - Native goroutines for asynchronous message consumption
   - Low memory footprint (~10-20MB per service)
   - Compiled binaries (no runtime dependencies)
   - Excellent connection pooling and channel management
   - Built-in context support for graceful shutdown

3. **Deployment Simplicity**
   - Single binary distribution
   - Cross-compilation for Linux containers
   - No dependency management issues
   - Small container image size

4. **Service Alignment**
   - **Cart Service**: Already implemented in Go → native integration
   - **Product Catalog**: Python → use native Python library (now available!)
   - **Order Service**: Java → can use Go via CLI/subprocess or native Java wrapper
   - **Future Services**: Go is becoming our standard for backend services

#### Python Library (Implemented)

**Update**: A full-featured Python library has been implemented and is production-ready.
Python services should use the native Python library directly instead of CLI wrappers.

**Java:**
- ❌ Heavy runtime (JVM overhead)
- ❌ Slower startup times
- ❌ More complex dependency management
- ✅ Excellent Spring AMQP library
- ✅ Strong type safety

**Verdict**: Native libraries for each language provide the best developer experience.

## Architecture

### Two-Tier Design

```
┌─────────────────────────────────────────────────┐
│         Go Core Library (Tier 1)                │
│  - RabbitMQ connection management               │
│  - Vault credential integration                 │
│  - Publisher/Consumer interfaces                │
│  - Event schemas and serialization              │
│  - Retry logic and error handling               │
└─────────────────┬───────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌────────┐   ┌────────┐   ┌────────┐
│  CLI   │   │  HTTP  │   │  gRPC  │
│  Tool  │   │  API   │   │  API   │
└────┬───┘   └────┬───┘   └────┬───┘
     │            │            │
┌────┴────────────┴────────────┴────┐
│   Language Wrappers (Tier 2)      │
│  - Python wrapper                 │
│  - Java wrapper                   │
│  - JavaScript/Node.js wrapper     │
└───────────────────────────────────┘
```

### Tier 1: Go Core Library

The foundation library providing production-ready messaging capabilities.

**Repository**: `shopping-cart-mq` (new repository)

**Key Components**:

1. **Connection Manager**
   - Vault integration for dynamic credentials
   - Connection pooling and recovery
   - Health checks and monitoring
   - Graceful shutdown handling

2. **Publisher Interface**
   - Type-safe event publishing
   - Routing key management
   - Confirmation tracking
   - Retry with exponential backoff

3. **Consumer Interface**
   - Message acknowledgment strategies
   - Concurrent processing with worker pools
   - Dead letter queue handling
   - Idempotent message processing

4. **Event Schemas**
   - Strongly-typed event definitions
   - JSON serialization/deserialization
   - Schema versioning support
   - Validation

### Tier 2: Language-Specific Wrappers

Lightweight adapters for non-Go services.

**Three Integration Options**:

#### Option A: CLI Tool (Simplest)
Services invoke Go binary as subprocess:
```bash
sc-mq-publisher order.created '{"orderId":"123","amount":99.99}'
```

**Pros**:
- Zero dependencies
- Works with any language
- Simple deployment

**Cons**:
- Process overhead per message
- No type safety
- Limited error handling

**Best For**: Low-frequency events (order creation, inventory updates)

#### Option B: HTTP API (Balanced)
Go service exposes REST API:
```http
POST /publish/order.created
Content-Type: application/json

{"orderId":"123","amount":99.99}
```

**Pros**:
- Language-agnostic
- Standard HTTP tooling
- Better error handling
- Connection pooling

**Cons**:
- Additional HTTP hop (latency)
- Need to deploy separate service

**Best For**: Medium-frequency events, heterogeneous environments

#### Option C: gRPC API (Advanced)
Go service exposes gRPC interface:
```protobuf
service MessageQueue {
  rpc PublishOrderCreated(OrderCreatedEvent) returns (PublishResponse);
  rpc ConsumeOrderCreated(ConsumeRequest) returns (stream OrderCreatedEvent);
}
```

**Pros**:
- High performance (Protocol Buffers)
- Bidirectional streaming
- Strong typing
- Code generation for all languages

**Cons**:
- More complex setup
- Proto file management
- Higher learning curve

**Best For**: High-frequency events, performance-critical paths

### Recommended Approach

**For Shopping Cart Platform**:

1. **Cart Service (Go)**: Use Tier 1 library directly (native Go import)
2. **Product Catalog (Python)**: Use **Option A (CLI)** initially, migrate to Option B if needed
3. **Order Service (Java)**: Use **Option A (CLI)** initially, migrate to Option C for high throughput
4. **Frontend (Node.js)**: Use **Option B (HTTP API)** for admin actions

**Rationale**: Start simple (CLI), optimize when needed (HTTP/gRPC).

## Library Structure

### Repository Layout

```
shopping-cart-mq/
├── go.mod
├── go.sum
├── README.md
├── LICENSE
│
├── pkg/
│   ├── rabbitmq/
│   │   ├── client.go          # Core RabbitMQ client with Vault integration
│   │   ├── client_test.go
│   │   ├── publisher.go       # Publisher interface and implementation
│   │   ├── publisher_test.go
│   │   ├── consumer.go        # Consumer interface and implementation
│   │   ├── consumer_test.go
│   │   ├── config.go          # Configuration structures
│   │   └── errors.go          # Custom error types
│   │
│   ├── events/
│   │   ├── order.go           # Order event types
│   │   ├── order_test.go
│   │   ├── inventory.go       # Inventory event types
│   │   ├── cart.go            # Cart event types
│   │   └── schema.go          # Common schema utilities
│   │
│   └── vault/
│       ├── credentials.go     # Vault credential fetching
│       └── credentials_test.go
│
├── cmd/
│   ├── publisher/             # CLI tool: sc-mq-publisher
│   │   ├── main.go
│   │   └── README.md
│   │
│   ├── consumer/              # CLI tool: sc-mq-consumer
│   │   ├── main.go
│   │   └── README.md
│   │
│   ├── http-api/              # Optional HTTP API server
│   │   ├── main.go
│   │   ├── handlers.go
│   │   └── README.md
│   │
│   └── grpc-api/              # Optional gRPC API server
│       ├── main.go
│       ├── server.go
│       └── README.md
│
├── api/
│   ├── proto/                 # gRPC protocol definitions
│   │   └── messagequeue.proto
│   └── openapi/               # HTTP API OpenAPI spec
│       └── messagequeue.yaml
│
├── examples/
│   ├── go/
│   │   ├── publisher/         # Go publisher example
│   │   │   └── main.go
│   │   └── consumer/          # Go consumer example
│   │       └── main.go
│   │
│   ├── python/
│   │   ├── wrapper.py         # Python wrapper for CLI tool
│   │   ├── publisher.py       # Example publisher
│   │   └── consumer.py        # Example consumer
│   │
│   ├── java/
│   │   ├── src/main/java/
│   │   │   └── com/shoppingcart/mq/
│   │   │       ├── Wrapper.java      # Java wrapper for CLI tool
│   │   │       ├── Publisher.java    # Example publisher
│   │   │       └── Consumer.java     # Example consumer
│   │   └── pom.xml
│   │
│   └── nodejs/
│       ├── wrapper.js         # Node.js wrapper for HTTP API
│       ├── publisher.js       # Example publisher
│       └── consumer.js        # Example consumer
│
├── docs/
│   ├── quick-start.md         # Getting started guide
│   ├── architecture.md        # Architecture overview
│   ├── go-integration.md      # Go integration guide
│   ├── python-integration.md  # Python integration guide
│   ├── java-integration.md    # Java integration guide
│   ├── nodejs-integration.md  # Node.js integration guide
│   ├── vault-integration.md   # Vault credential management
│   └── troubleshooting.md     # Common issues and solutions
│
└── scripts/
    ├── build.sh               # Build all binaries
    ├── test.sh                # Run tests
    └── install.sh             # Install binaries to $GOPATH/bin
```

## Core Interfaces

### Publisher Interface

```go
package rabbitmq

import "context"

// Publisher handles publishing messages to RabbitMQ exchanges
type Publisher interface {
    // PublishOrderCreated publishes an order.created event
    PublishOrderCreated(ctx context.Context, event *events.OrderCreated) error

    // PublishOrderCompleted publishes an order.completed event
    PublishOrderCompleted(ctx context.Context, event *events.OrderCompleted) error

    // PublishStockUpdated publishes a stock.updated event
    PublishStockUpdated(ctx context.Context, event *events.StockUpdated) error

    // PublishCartAbandoned publishes a cart.abandoned event
    PublishCartAbandoned(ctx context.Context, event *events.CartAbandoned) error

    // Close gracefully closes the publisher
    Close() error
}

// PublisherConfig configures the publisher
type PublisherConfig struct {
    RabbitMQURL      string
    VaultAddr        string
    VaultToken       string
    VaultRolePath    string // e.g., "rabbitmq/creds/order-publisher"
    ExchangeName     string
    ConfirmPublish   bool   // Wait for broker confirmation
    MaxRetries       int
    RetryBackoff     time.Duration
}

// NewPublisher creates a new publisher instance
func NewPublisher(config PublisherConfig) (Publisher, error)
```

### Consumer Interface

```go
package rabbitmq

import "context"

// Consumer handles consuming messages from RabbitMQ queues
type Consumer interface {
    // ConsumeOrderCreated consumes order.created events
    ConsumeOrderCreated(ctx context.Context, handler OrderCreatedHandler) error

    // ConsumeStockUpdated consumes stock.updated events
    ConsumeStockUpdated(ctx context.Context, handler StockUpdatedHandler) error

    // Close gracefully closes the consumer
    Close() error
}

// OrderCreatedHandler processes order.created events
type OrderCreatedHandler func(ctx context.Context, event *events.OrderCreated) error

// StockUpdatedHandler processes stock.updated events
type StockUpdatedHandler func(ctx context.Context, event *events.StockUpdated) error

// ConsumerConfig configures the consumer
type ConsumerConfig struct {
    RabbitMQURL      string
    VaultAddr        string
    VaultToken       string
    VaultRolePath    string // e.g., "rabbitmq/creds/order-consumer"
    QueueName        string
    PrefetchCount    int    // Number of messages to prefetch
    AutoAck          bool   // Automatically acknowledge messages
    WorkerCount      int    // Number of concurrent workers
}

// NewConsumer creates a new consumer instance
func NewConsumer(config ConsumerConfig) (Consumer, error)
```

### Event Schemas

```go
package events

import "time"

// OrderCreated represents an order.created event
type OrderCreated struct {
    OrderID     string              `json:"orderId"`
    UserID      string              `json:"userId"`
    Items       []OrderItem         `json:"items"`
    TotalAmount float64             `json:"totalAmount"`
    Currency    string              `json:"currency"`
    Timestamp   time.Time           `json:"timestamp"`
    Metadata    map[string]string   `json:"metadata,omitempty"`
}

// OrderItem represents an item in an order
type OrderItem struct {
    ProductID   string  `json:"productId"`
    Quantity    int     `json:"quantity"`
    UnitPrice   float64 `json:"unitPrice"`
    ProductName string  `json:"productName"`
}

// StockUpdated represents a stock.updated event
type StockUpdated struct {
    ProductID   string    `json:"productId"`
    OldStock    int       `json:"oldStock"`
    NewStock    int       `json:"newStock"`
    Warehouse   string    `json:"warehouse"`
    Timestamp   time.Time `json:"timestamp"`
}

// CartAbandoned represents a cart.abandoned event
type CartAbandoned struct {
    CartID      string              `json:"cartId"`
    UserID      string              `json:"userId"`
    Items       []OrderItem         `json:"items"`
    TotalAmount float64             `json:"totalAmount"`
    AbandonedAt time.Time           `json:"abandonedAt"`
}
```

## Integration Examples

### Go Service (Direct Integration)

```go
package main

import (
    "context"
    "log"

    "github.com/user/shopping-cart-mq/pkg/rabbitmq"
    "github.com/user/shopping-cart-mq/pkg/events"
)

func main() {
    // Create publisher
    publisher, err := rabbitmq.NewPublisher(rabbitmq.PublisherConfig{
        VaultAddr:     "https://vault.vault.svc.cluster.local:8200",
        VaultToken:    getVaultToken(),
        VaultRolePath: "rabbitmq/creds/order-publisher",
        ExchangeName:  "orders.events",
        ConfirmPublish: true,
        MaxRetries:    3,
    })
    if err != nil {
        log.Fatal(err)
    }
    defer publisher.Close()

    // Publish event
    event := &events.OrderCreated{
        OrderID:     "order-123",
        UserID:      "user-456",
        TotalAmount: 99.99,
        Currency:    "USD",
    }

    if err := publisher.PublishOrderCreated(context.Background(), event); err != nil {
        log.Fatalf("Failed to publish: %v", err)
    }

    log.Println("Order created event published successfully")
}
```

### Python Service (CLI Wrapper)

```python
# shopping_cart_mq/wrapper.py
import subprocess
import json
from typing import Dict, Any

class RabbitMQPublisher:
    """Wrapper for sc-mq-publisher CLI tool"""

    def __init__(self, cli_path: str = "sc-mq-publisher"):
        self.cli_path = cli_path

    def publish_order_created(self, event: Dict[str, Any]) -> None:
        """Publish order.created event"""
        result = subprocess.run(
            [self.cli_path, "order.created", json.dumps(event)],
            capture_output=True,
            text=True,
            check=True
        )

        if result.returncode != 0:
            raise Exception(f"Failed to publish: {result.stderr}")

# Example usage
if __name__ == "__main__":
    publisher = RabbitMQPublisher()

    event = {
        "orderId": "order-123",
        "userId": "user-456",
        "totalAmount": 99.99,
        "currency": "USD"
    }

    publisher.publish_order_created(event)
    print("Order created event published successfully")
```

### Java Service (CLI Wrapper)

```java
// com/shoppingcart/mq/RabbitMQPublisher.java
package com.shoppingcart.mq;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Map;

public class RabbitMQPublisher {
    private final String cliPath;
    private final ObjectMapper mapper;

    public RabbitMQPublisher(String cliPath) {
        this.cliPath = cliPath;
        this.mapper = new ObjectMapper();
    }

    public void publishOrderCreated(Map<String, Object> event) throws IOException, InterruptedException {
        String eventJson = mapper.writeValueAsString(event);

        ProcessBuilder pb = new ProcessBuilder(
            cliPath,
            "order.created",
            eventJson
        );

        Process process = pb.start();
        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Failed to publish event");
        }
    }
}

// Example usage
public class Main {
    public static void main(String[] args) throws Exception {
        RabbitMQPublisher publisher = new RabbitMQPublisher("sc-mq-publisher");

        Map<String, Object> event = Map.of(
            "orderId", "order-123",
            "userId", "user-456",
            "totalAmount", 99.99,
            "currency", "USD"
        );

        publisher.publishOrderCreated(event);
        System.out.println("Order created event published successfully");
    }
}
```

## Vault Integration

### Dynamic Credential Flow

```
1. Service starts up
   ↓
2. Library fetches credentials from Vault
   vault read rabbitmq/creds/order-publisher
   ↓
3. Vault generates temporary RabbitMQ user
   username: v-k8s-order-pub-ABC123-1234567890
   password: <random-20-char-string>
   ttl: 1 hour
   ↓
4. Library connects to RabbitMQ with credentials
   ↓
5. Before TTL expires, library refreshes credentials
   ↓
6. On shutdown, credentials are revoked automatically
```

### Configuration

```go
type VaultConfig struct {
    // Vault server address
    Address string

    // Vault token (from K8s ServiceAccount or environment)
    Token string

    // Path to RabbitMQ credentials role
    // Example: "rabbitmq/creds/order-publisher"
    RolePath string

    // How long before expiration to refresh (default: 5 minutes)
    RefreshBefore time.Duration
}
```

## Development Roadmap

### Phase 1: Core Library (Week 1)
- [ ] Implement connection manager with Vault integration
- [ ] Implement publisher interface
- [ ] Implement consumer interface
- [ ] Define event schemas for orders and inventory
- [ ] Write comprehensive unit tests
- [ ] Create Go examples

### Phase 2: CLI Tools (Week 1)
- [ ] Build `sc-mq-publisher` CLI tool
- [ ] Build `sc-mq-consumer` CLI tool
- [ ] Add comprehensive CLI documentation
- [ ] Create shell script examples

### Phase 3: Language Wrappers (Week 2)
- [ ] Implement Python CLI wrapper
- [ ] Implement Java CLI wrapper
- [ ] Create Python/Java examples
- [ ] Write integration guides

### Phase 4: Optional APIs (Week 3)
- [ ] Implement HTTP API server (if needed)
- [ ] Implement gRPC API server (if needed)
- [ ] Create Node.js HTTP client wrapper
- [ ] Performance benchmarking

### Phase 5: Production Readiness (Week 4)
- [ ] Add comprehensive logging (structured logging)
- [ ] Add Prometheus metrics
- [ ] Add distributed tracing (OpenTelemetry)
- [ ] Create deployment manifests
- [ ] Write operational runbooks
- [ ] Load testing and optimization

## Testing Strategy

### Unit Tests
```go
// pkg/rabbitmq/publisher_test.go
func TestPublisher_PublishOrderCreated(t *testing.T) {
    // Mock RabbitMQ connection
    // Test successful publish
    // Test retry logic
    // Test error handling
}
```

### Integration Tests
```go
// integration_test.go
func TestEndToEnd_OrderCreatedFlow(t *testing.T) {
    // Start test RabbitMQ instance
    // Publish event
    // Consume event
    // Verify event data
}
```

### Load Tests
```bash
# Test sustained throughput
wrk -t4 -c100 -d60s --script=publish-order.lua http://localhost:8080/publish

# Test burst traffic
vegeta attack -duration=30s -rate=1000 -targets=targets.txt | vegeta report
```

## Performance Targets

### Throughput
- **Publisher**: 10,000 messages/second (single instance)
- **Consumer**: 5,000 messages/second (single instance with 10 workers)

### Latency
- **Publish latency**: p50 < 5ms, p99 < 20ms
- **End-to-end latency**: p50 < 50ms, p99 < 200ms

### Resource Usage
- **Memory**: < 50MB per service
- **CPU**: < 0.1 core at idle, < 1 core at peak

## Security Considerations

### Credential Management
- ✅ Vault dynamic credentials (1-hour TTL)
- ✅ Automatic credential rotation
- ✅ No hardcoded credentials
- ✅ Least-privilege access (publisher vs consumer roles)

### Network Security
- ✅ TLS for RabbitMQ connections
- ✅ Istio mTLS between services
- ✅ NetworkPolicy restrictions

### Message Security
- ✅ Message validation (schema enforcement)
- ✅ No sensitive data in messages (use references)
- ✅ Audit logging for all publish/consume operations

## Monitoring and Observability

### Metrics (Prometheus)
```
# Publisher metrics
rabbitmq_published_total{event_type, status}
rabbitmq_publish_duration_seconds{event_type}
rabbitmq_publish_errors_total{event_type, error_type}

# Consumer metrics
rabbitmq_consumed_total{event_type, status}
rabbitmq_consume_duration_seconds{event_type}
rabbitmq_consume_errors_total{event_type, error_type}

# Connection metrics
rabbitmq_connections_active
rabbitmq_credential_refreshes_total
```

### Logging
```json
{
  "timestamp": "2025-01-12T10:30:00Z",
  "level": "info",
  "event_type": "order.created",
  "order_id": "order-123",
  "action": "publish",
  "duration_ms": 12,
  "status": "success"
}
```

### Tracing
- OpenTelemetry integration
- Distributed traces across publish → queue → consume
- Integration with Jaeger/Tempo

## Migration Strategy

### Phase 1: Cart Service (Go)
- Week 1: Integrate library directly
- Week 1: Deploy to staging
- Week 2: Deploy to production
- Success criteria: 100% events published successfully

### Phase 2: Product Catalog (Python)
- Week 2: Implement CLI wrapper
- Week 3: Deploy to staging
- Week 3: Monitor performance
- Week 4: Deploy to production

### Phase 3: Order Service (Java)
- Week 3: Implement CLI wrapper
- Week 4: Deploy to staging
- Week 4: Performance tuning if needed
- Week 5: Deploy to production

## References

### External Documentation
- [RabbitMQ AMQP 0-9-1 Go Client](https://github.com/rabbitmq/amqp091-go)
- [Vault RabbitMQ Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/rabbitmq)
- [AMQP Protocol Specification](https://www.rabbitmq.com/resources/specs/amqp0-9-1.pdf)

### Internal Documentation
- [Message Queue Implementation Plan](../docs/plans/message-queue-implementation.md)
- [Vault Usage Guide](vault-usage-guide.md)
- [Infrastructure README](../README.md)

---

**Document Status**: Updated - Python, Go, Java Complete; .NET Planned
**Last Updated**: 2025-12-26
**Owner**: Platform Team

**Client Libraries:**
- Python: ✅ Complete (see `rabbitmq-client-library/python/`)
- Go: ✅ Complete (see `rabbitmq-client-go/`)
- Java: ✅ Complete (see `rabbitmq-client-java/`)
- .NET: 📋 Planned (repository `rabbitmq-client-dotnet/`)
