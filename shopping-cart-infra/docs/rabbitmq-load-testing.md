# RabbitMQ Load Testing & Queue Management Guide

This guide covers load testing, alerting, and queue management operations for the RabbitMQ cluster.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Makefile Commands](#makefile-commands)
3. [Load Testing](#load-testing)
4. [Queue Management](#queue-management)
5. [Alerting](#alerting)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# From shopping-cart-infra directory
cd /path/to/shopping-cart-infra

# Check infrastructure status
make status

# Run a quick load test
make load-test-quick

# Check queue status
make rabbitmq-queues

# View alerts
make alerts

# Clean up test messages
make purge
```

---

## Makefile Commands

Run `make help` to see all available commands. Key commands for testing and monitoring:

### Load Testing

| Command | Description |
|---------|-------------|
| `make load-test` | Run quick load test (alias for load-test-quick) |
| `make load-test-quick` | Quick test: 50 msgs/sec for 5s (~250 messages) |
| `make load-test-burst` | Burst test: 1000 msgs/sec for 30s (~30,000 messages) |
| `make load-test-sustained` | Sustained test: 100 msgs/sec for 10 min |
| `make load-test-stress` | Stress test with ramp-up pattern |
| `make load-test-alert` | Build queue depth to trigger alerts |

### Queue Management

| Command | Description |
|---------|-------------|
| `make rabbitmq-queues` | List all queues with message counts |
| `make purge` | Purge all messages from load-test-queue |
| `make purge-queue QUEUE=name` | Purge all messages from specific queue |
| `make purge-count COUNT=N QUEUE=name` | Purge first N messages from queue |
| `make purge-all` | Purge ALL queues (requires confirmation) |
| `make cleanup` | Delete test queues and exchanges |

### Monitoring

| Command | Description |
|---------|-------------|
| `make alerts` | Show RabbitMQ alert status (no port-forward needed) |
| `make rabbitmq-status` | Show RabbitMQ cluster status |
| `make grafana` | Open Grafana dashboard (port-forward) |
| `make prometheus` | Open Prometheus UI (port-forward) |
| `make alertmanager` | Open Alertmanager UI (port-forward) |

---

## Load Testing

### Using the Helper Script Directly

The `bin/test-rabbitmq-load.sh` script provides more options than the Makefile:

```bash
./bin/test-rabbitmq-load.sh <command> [options]
```

### Available Commands

| Command | Description | Default Rate | Default Duration |
|---------|-------------|--------------|------------------|
| `quick` | Quick sanity test | 50 msg/s | 5s |
| `burst` | High-volume burst | 1000 msg/s | 30s |
| `sustained` | Sustained load | 100 msg/s | 10 min |
| `stress` | Stress with ramp-up | 500 msg/s max | 5 min |
| `trigger-alert` | Build queue for alerts | 500 msg/s | 60s |

### Custom Rate and Duration

Override defaults with `-r` (rate) and `-d` (duration) flags:

```bash
# 200 messages/sec for 60 seconds
./bin/test-rabbitmq-load.sh burst -r 200 -d 60

# Sustained load at 50 msgs/sec for 5 minutes
./bin/test-rabbitmq-load.sh sustained -r 50 -d 300
```

### Test Scenarios

#### Quick Health Check
```bash
make load-test-quick
# Expected: ~250 messages published in 5s
# Use case: Verify RabbitMQ is working after deployment
```

#### Burst Test
```bash
make load-test-burst
# Expected: ~30,000 messages in 30s
# Use case: Test high-throughput scenarios
```

#### Alert Testing
```bash
make load-test-alert
# Expected: ~30,000 messages, triggers alerts
# Use case: Verify Prometheus alerts are working
```

### Environment Variables

Configure RabbitMQ connection (auto-configured for K8s NodePort):

| Variable | Default | Description |
|----------|---------|-------------|
| `RABBITMQ_HOST` | localhost | RabbitMQ hostname |
| `RABBITMQ_PORT` | 30672 | AMQP port (NodePort) |
| `RABBITMQ_USERNAME` | demo | Username |
| `RABBITMQ_PASSWORD` | demo | Password |

Example with custom settings:
```bash
RABBITMQ_HOST=rabbitmq.example.com RABBITMQ_PORT=5672 ./bin/test-rabbitmq-load.sh quick
```

---

## Queue Management

### Purge Commands

#### Purge All Messages from a Queue

```bash
# Default queue (load-test-queue)
make purge

# Specific queue
make purge-queue QUEUE=order.processing

# Using script directly
./bin/test-rabbitmq-load.sh purge myqueue
```

#### Purge First N Messages

Useful for partial cleanup without removing all messages:

```bash
# Purge first 100 messages from load-test-queue
make purge-count COUNT=100

# Purge first 50 messages from specific queue
make purge-count COUNT=50 QUEUE=order.processing

# Using script directly
./bin/test-rabbitmq-load.sh purge-count 100 myqueue
```

#### Purge All Queues

**WARNING**: This affects all queues, not just test queues!

```bash
make purge-all
# Requires typing "yes" to confirm
```

### Cleanup Test Resources

Delete test queues and exchanges entirely:

```bash
make cleanup
# Removes: load-test-queue, load-test-exchange
```

### Purge Capabilities & Limitations

| Operation | Supported | Method |
|-----------|-----------|--------|
| Purge all messages from queue | Yes | `rabbitmqctl purge_queue` |
| Purge first N messages | Yes | Management API with ack |
| Purge by message content | No | Consume, filter, republish |
| Purge range (X to Y) | No | Not supported by RabbitMQ |
| Purge last N messages | No | Queue is FIFO |

---

## Alerting

### View Alert Status

```bash
make alerts
```

Output shows all RabbitMQ alerts with their current state:

```
=== Prometheus RabbitMQ Alerts ===

Alert Name                               State   Severity  Details
--------------------------------------------------------------------------------
RabbitMQTestQueueNotEmpty               firing       info  queue=load-test-queue
RabbitMQDown                          inactive   critical
RabbitMQQueueDepthHigh                inactive    warning
RabbitMQNoConsumers                    pending    warning  queue=order.processing
...
```

### Alert States

| State | Description |
|-------|-------------|
| `inactive` | Condition is false, alert not triggered |
| `pending` | Condition is true, waiting for `for:` duration |
| `firing` | Condition true for required duration, alert active |

### Alert Lifecycle

```
Condition true     Condition true       Condition false
     │             for "for:" duration        │
     ▼                    ▼                   ▼
 [inactive] ──────► [pending] ──────► [firing] ──────► [inactive]
                         │                              ▲
                         └──────────────────────────────┘
                         (resolves if condition becomes
                          false before "for:" duration)
```

**Alerts automatically resolve** when the underlying condition is no longer true. No manual reset is needed.

### Available Alerts

| Alert | Severity | Threshold | Description |
|-------|----------|-----------|-------------|
| `RabbitMQTestQueueNotEmpty` | info | >50 messages | Test alert for load-test-queue |
| `RabbitMQDown` | critical | node unavailable | RabbitMQ node is down |
| `RabbitMQClusterPartition` | critical | partition detected | Network partition in cluster |
| `RabbitMQQueueDepthHigh` | warning | >10,000 messages | Queue depth is high |
| `RabbitMQQueueDepthCritical` | critical | >50,000 messages | Queue depth is critical |
| `RabbitMQNoConsumers` | warning | 0 consumers, >0 messages | Queue has no consumers |
| `RabbitMQUnackedMessagesHigh` | warning | >1,000 unacked | Slow consumer processing |
| `RabbitMQMemoryHigh` | warning | >80% memory | Memory usage high |
| `RabbitMQMemoryCritical` | critical | >95% memory | Memory usage critical |
| `RabbitMQDiskSpaceLow` | warning | <2x limit | Disk space low |
| `RabbitMQDLQNotEmpty` | warning | >0 in DLQ | Dead letter queue has messages |
| `RabbitMQDLQGrowing` | critical | >100/hour in DLQ | DLQ growing rapidly |

### Alert Destinations

Current configuration sends alerts to:
- **Prometheus UI**: View at http://localhost:9090/alerts (via `make prometheus`)
- **Grafana**: Alert panels in dashboards (via `make grafana`)
- **Alertmanager**: Manages routing (via `make alertmanager`)

To enable email/Slack notifications, see:
- [Alertmanager Configuration](../observability-stack/manifests/alertmanager/alertmanager-config.yaml)

---

## Monitoring

### Grafana Dashboard

```bash
make grafana
# Opens http://localhost:3000
# Dashboard: RabbitMQ Overview
```

### Prometheus Queries

Access Prometheus UI:
```bash
make prometheus
# Opens http://localhost:9090
```

Useful queries:

```promql
# Per-queue message count
rabbitmq_detailed_queue_messages_ready

# Specific queue depth
rabbitmq_detailed_queue_messages_ready{queue="load-test-queue"}

# Consumer count per queue
rabbitmq_detailed_queue_consumers

# Memory usage percentage
rabbitmq_process_resident_memory_bytes / rabbitmq_resident_memory_limit_bytes

# Message publish rate
rate(rabbitmq_channel_messages_published_total[5m])
```

### Queue Status via CLI

```bash
# Quick status check
./bin/test-rabbitmq-load.sh status

# Via Makefile
make rabbitmq-queues

# Direct kubectl
kubectl exec -n shopping-cart-data rabbitmq-0 -- \
  rabbitmqctl list_queues name messages consumers
```

---

## Troubleshooting

### Load Test Fails to Connect

```bash
# Check RabbitMQ is accessible
curl -u "$RABBITMQ_USERNAME:$RABBITMQ_PASSWORD" http://localhost:15672/api/overview

# Verify NodePort is working
kubectl get svc -n shopping-cart-data rabbitmq

# Check pod status
kubectl get pods -n shopping-cart-data -l app=rabbitmq
```

### Alerts Not Firing

1. **Check metrics are being scraped:**
   ```bash
   make prometheus
   # Query: rabbitmq_detailed_queue_messages_ready
   # Should show per-queue metrics
   ```

2. **Verify ServiceMonitor is configured:**
   ```bash
   kubectl get servicemonitor -n monitoring rabbitmq -o yaml
   # Should have /metrics/detailed endpoint
   ```

3. **Check alert rules are loaded:**
   ```bash
   make alerts
   # All alerts should be listed
   ```

### High Memory After Load Test

```bash
# Purge test messages
make purge

# Force garbage collection
kubectl exec -n shopping-cart-data rabbitmq-0 -- \
  rabbitmqctl eval "garbage_collect()."

# Check memory breakdown
kubectl exec -n shopping-cart-data rabbitmq-0 -- \
  rabbitmqctl status | grep -A20 "Memory"
```

### Queue Stuck with Messages

```bash
# Check for consumers
kubectl exec -n shopping-cart-data rabbitmq-0 -- \
  rabbitmqctl list_consumers

# Purge if needed
make purge-queue QUEUE=stuck-queue

# Or delete queue entirely
kubectl exec -n shopping-cart-data rabbitmq-0 -- \
  rabbitmqctl delete_queue stuck-queue
```

---

## Backup & Recovery

### Create Backup

```bash
# Backup definitions (exchanges, queues, bindings, users)
make rabbitmq-backup

# List available backups
make rabbitmq-backup-list
```

### Restore from Backup

```bash
# Restore from specific backup
make rabbitmq-restore BACKUP=backups/rabbitmq/20241227-120000

# Or using script directly
./bin/rabbitmq-restore.sh backups/rabbitmq/20241227-120000
```

### What's Backed Up

| Component | Included | Notes |
|-----------|----------|-------|
| Exchanges | Yes | Type, durability, auto-delete settings |
| Queues | Yes | Configuration only, not messages |
| Bindings | Yes | Exchange-queue-routing key mappings |
| Users | Yes | Usernames, password hashes, tags |
| Policies | Yes | Queue/exchange policies |
| Messages | Optional | Use `--messages` flag (experimental) |

### Backup Best Practices

1. **Schedule regular backups** - At least daily for production
2. **Store backups externally** - Copy archives to S3, GCS, or external storage
3. **Test restores periodically** - Verify backups are usable
4. **Backup before changes** - Always backup before major configuration changes

---

## Related Documentation

- [RabbitMQ Operations Guide](rabbitmq-operations.md) - Cluster operations, scaling, backup
- [Message Queue Implementation Plan](plans/message-queue-implementation.md) - Architecture design
- [Vault Integration](vault-usage-guide.md) - Credential management

---

**Last Updated**: 2025-12-27
**Owner**: Platform Team
