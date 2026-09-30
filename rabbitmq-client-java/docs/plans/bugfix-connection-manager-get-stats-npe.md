# Bugfix: ConnectionManager.getStats() NPE on first health check

**Branch:** `fix/connection-manager-get-stats-npe`
**Files:** `rabbitmq-client/src/main/java/com/shoppingcart/rabbitmq/connection/ConnectionManager.java`
**Agent:** Codex

---

## Problem

`CachingConnectionFactory.getCacheProperties()` throws `NullPointerException` when called before
any AMQP channel has been created. This happens on every `/actuator/health` probe during pod
startup, causing `RabbitMQHealthIndicator` to return DOWN, the startup probe to fail repeatedly,
and the pod to be killed.

**Issue:** `docs/issues/2026-04-06-connection-manager-get-stats-npe.md`

---

## Before You Start

1. `git -C rabbitmq-client-java checkout -b fix/connection-manager-get-stats-npe origin/fix/ci-stabilization`
2. Read `rabbitmq-client/src/main/java/com/shoppingcart/rabbitmq/connection/ConnectionManager.java` lines 204–224
3. **Branch:** `fix/connection-manager-get-stats-npe` — never commit to `main`

---

## Fix

### Change 1 — `ConnectionManager.java`: guard `getCacheProperties()` against NPE

**Exact old block (lines 207–224):**

```java
    public ConnectionStats getStats() {
        if (connectionFactory == null) {
            return new ConnectionStats(0, 0, 0, false);
        }

        var cacheProperties = connectionFactory.getCacheProperties();
        int channelCacheSize = Integer.parseInt(
                cacheProperties.getOrDefault("channelCacheSize", "0").toString());
        int idleChannels = Integer.parseInt(
                cacheProperties.getOrDefault("idleChannelsNotTx", "0").toString());

        return new ConnectionStats(
                channelCacheSize,
                channelCacheSize - idleChannels,
                idleChannels,
                isHealthy()
        );
    }
```

**Exact new block:**

```java
    public ConnectionStats getStats() {
        if (connectionFactory == null) {
            return new ConnectionStats(0, 0, 0, false);
        }

        int channelCacheSize = 0;
        int idleChannels = 0;
        try {
            var cacheProperties = connectionFactory.getCacheProperties();
            channelCacheSize = Integer.parseInt(
                    cacheProperties.getOrDefault("channelCacheSize", "0").toString());
            idleChannels = Integer.parseInt(
                    cacheProperties.getOrDefault("idleChannelsNotTx", "0").toString());
        } catch (Exception ignored) {
            // getCacheProperties() throws NPE before any channel is opened (Spring AMQP 3.1.0)
        }

        return new ConnectionStats(
                channelCacheSize,
                channelCacheSize - idleChannels,
                idleChannels,
                isHealthy()
        );
    }
```

---

## Files Changed

| File | Change |
|------|--------|
| `rabbitmq-client/src/main/java/com/shoppingcart/rabbitmq/connection/ConnectionManager.java` | wrap `getCacheProperties()` in try-catch |

---

## Rules

- No other files touched
- `mvn -pl rabbitmq-client compile` must pass with zero errors
- Do NOT bump the version in `pom.xml`

---

## Definition of Done

- [ ] `getStats()` no longer throws when called before any channel is opened
- [ ] `mvn -pl rabbitmq-client compile` passes
- [ ] Committed and pushed to `fix/connection-manager-get-stats-npe`
- [ ] memory-bank updated with commit SHA and task status

**Commit message (exact):**
```
fix(connection-manager): guard getCacheProperties() against NPE before first channel open
```

---

## What NOT to Do

- Do NOT create a PR
- Do NOT skip pre-commit hooks (`--no-verify`)
- Do NOT modify any file other than `ConnectionManager.java`
- Do NOT bump `pom.xml` version
- Do NOT commit to `main`
