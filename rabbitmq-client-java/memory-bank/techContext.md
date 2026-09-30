# Tech Context: rabbitmq-client-java

## Language & Runtime

- **Java 21** (LTS; virtual threads available via Project Loom)
- **Maven 3.9+** multi-module build
- Group ID: `com.shoppingcart`
- Parent artifact: `rabbitmq-client-parent:1.0.0-SNAPSHOT`

## Module Structure

| Module | Artifact ID | JAR Type | Purpose |
|---|---|---|---|
| `rabbitmq-client/` | `rabbitmq-client` | Library JAR (no main class) | Core library; the dependency consumers add |
| `rabbitmq-cli/` | `rabbitmq-cli` | Executable Spring Boot JAR | CLI publisher and consumer tools |
| `rabbitmq-examples/` | `rabbitmq-examples` | Executable Spring Boot JAR | Demo and example applications |

## Key Dependencies (from POMs)

### Core Library (`rabbitmq-client`)
| Dependency | Purpose |
|---|---|
| `spring-boot-starter-amqp` | Spring AMQP: `RabbitTemplate`, `SimpleMessageListenerContainer`, connection factory |
| `spring-cloud-starter-vault-config` | Spring Cloud Vault: `VaultTemplate`, auto-configured Vault client |
| `resilience4j-spring-boot3` | Resilience4j Spring Boot 3 auto-config |
| `resilience4j-circuitbreaker` | Circuit breaker state machine |
| `resilience4j-retry` | Retry with backoff |
| `micrometer-registry-prometheus` | Prometheus metrics exposition via `/actuator/prometheus` |
| `spring-boot-starter-actuator` | `/actuator/health`, `/actuator/health/rabbitMQ`, `/actuator/health/vault` |
| `spring-boot-starter-validation` | Jakarta Bean Validation for `@ConfigurationProperties` |
| `spring-boot-configuration-processor` | Generates IDE metadata for `application.yml` |
| `lombok` | `@Slf4j`, `@Data`, `@Builder`, `@Value`, `@RequiredArgsConstructor` |
| `spring-boot-starter-test` (test) | JUnit 5, Mockito, AssertJ |
| `spring-rabbit-test` (test) | Spring AMQP test utilities |
| `testcontainers:rabbitmq` (test) | RabbitMQ container for integration tests |
| `testcontainers:vault` (test) | Vault container for integration tests |
| `testcontainers:junit-jupiter` (test) | `@Testcontainers` + `@Container` annotations |

### Spring Boot BOM versions (managed by parent)
- Spring Boot: **3.2.0**
- Spring Cloud: **2023.0.0**
- Resilience4j BOM: **2.2.0**
- Testcontainers BOM: **1.19.3**

## Configuration

Configuration via `application.yml` under prefix `rabbitmq` (or environment variables using Spring's relaxed binding: `RABBITMQ_HOST`, `RABBITMQ_PORT`, etc.):

```yaml
rabbitmq:
  host: localhost            # RABBITMQ_HOST
  port: 5672                 # RABBITMQ_PORT
  vhost: /
  use-tls: false
  username: guest            # static creds; used when vault.enabled=false
  password: guest

  pool:
    size: 10
    prefetch-count: 10
    heartbeat: 60s
    max-idle-time: 10m
    acquire-timeout: 30s

  retry:
    max-attempts: 3
    initial-interval: 1s
    max-interval: 30s
    multiplier: 2.0
    jitter-factor: 0.1

  circuit-breaker:
    enabled: true
    failure-threshold: 5
    success-threshold: 2
    timeout: 30s
    sliding-window-size: 10
    failure-rate-threshold: 50   # percent

  vault:
    enabled: true
    role: rabbitmq-role
    backend: rabbitmq
    renewal-interval: 5m
    renewal-threshold: 0.8       # renew at 80% TTL

spring:
  cloud:
    vault:
      uri: http://localhost:8200
      token: ${VAULT_TOKEN}
```

## Dev Environment Setup

### Prerequisites
- Java 21: `brew install openjdk@21`; set `JAVA_HOME=/opt/homebrew/opt/openjdk@21`
- Maven 3.9+: `brew install maven`
- Docker (for integration tests and dev services)

### First-time Setup
```bash
# Install dependencies and build
mvn clean install -DskipTests

# Start local dev services (RabbitMQ + Vault)
make dev-start      # docker compose up -d
make dev-setup      # configures Vault for RabbitMQ credentials

# Run demo to verify setup
make demo
```

### Demo Profile
`rabbitmq-examples/src/main/resources/application-demo.yml`:
- Port: `30672` (Kubernetes NodePort for RabbitMQ)
- Credentials: `demo/demo` (static, no Vault)
- Vault: disabled
- Circuit breaker: disabled

Override for local port 5672:
```bash
RABBITMQ_HOST=localhost RABBITMQ_PORT=5672 RABBITMQ_USERNAME=guest RABBITMQ_PASSWORD=guest make demo
```

## CI/CD

- **GitHub Actions**: `.github/workflows/java-ci.yml` — build, test, coverage
- **Jenkins**: `Jenkinsfile` at project root

## Health & Metrics Endpoints (via Spring Actuator)

| Endpoint | Description |
|---|---|
| `/actuator/health` | Overall health |
| `/actuator/health/rabbitMQ` | RabbitMQ connection status |
| `/actuator/health/vault` | Vault credential status |
| `/actuator/prometheus` | Prometheus metrics scrape |
