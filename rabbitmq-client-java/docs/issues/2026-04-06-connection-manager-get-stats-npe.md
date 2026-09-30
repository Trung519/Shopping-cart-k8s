# Issue: ConnectionManager.getStats() NPE on first health check

**Date:** 2026-04-06
**Repo:** rabbitmq-client-java
**File:** `rabbitmq-client/src/main/java/com/shoppingcart/rabbitmq/connection/ConnectionManager.java`
**Symptom:** `order-service` pod CrashLoopBackOff — startup probe fails due to repeated health check exceptions

## Error

```
java.lang.NullPointerException: Cannot invoke "java.util.concurrent.atomic.AtomicInteger.get()"
  because the return value of "java.util.Map.get(Object)" is null
    at org.springframework.amqp.rabbit.connection.CachingConnectionFactory.getCacheProperties(CachingConnectionFactory.java:966)
    at com.shoppingcart.rabbitmq.connection.ConnectionManager.getStats(ConnectionManager.java:212)
    at com.shoppingcart.rabbitmq.health.RabbitMQHealthIndicator.health(RabbitMQHealthIndicator.java:22)
```

## Root Cause

`CachingConnectionFactory.getCacheProperties()` (Spring AMQP 3.1.0) throws `NullPointerException`
when the factory's internal channel cache has not yet been used. The cache map tracks `AtomicInteger`
counters per connection, but those counters are only populated when a channel is first opened.
On the first `/actuator/health` probe — which fires before any message is published — no channels
have been created yet, so `getCacheProperties()` returns a map with null `AtomicInteger` values
and crashes when it tries to call `.get()` on them.

`ConnectionManager.getStats()` calls `getCacheProperties()` without guarding against this NPE,
causing `RabbitMQHealthIndicator` to return `Health.down()` for every startup probe. After
`failureThreshold * periodSeconds`, Kubernetes kills the pod.

## Timeline

1. `ConnectionManager.initialize()` creates `CachingConnectionFactory` and connects to RabbitMQ
2. `/actuator/health` probe fires (startup, periodSeconds=5)
3. `RabbitMQHealthIndicator.health()` → `isHealthy()` returns `true` (connection is open)
4. `getStats()` calls `getCacheProperties()` → NPE (no channels opened yet)
5. `health()` catch block returns `Health.down()` → probe returns 503
6. After 30 failures (150s), pod is killed

## Fix

Wrap `getCacheProperties()` in a try-catch in `ConnectionManager.getStats()`.
Spec: `docs/plans/bugfix-connection-manager-get-stats-npe.md`
