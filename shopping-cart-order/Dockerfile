# Shopping Cart Order Service - Multi-stage Dockerfile
# Java 21 / Spring Boot 3.2

# =============================================================================
# Stage 1: Build
# =============================================================================
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app

# Install Maven
RUN apk add --no-cache git maven

ARG RABBITMQ_CLIENT_COMMIT=72412443e2dddb96c714488b0f796146e9e55036

# Copy build descriptors first for caching
COPY pom.xml checkstyle.xml ./
COPY vendor/rabbitmq-client-1.0.1.pom /tmp/rabbitmq-client.pom

# Build the pinned shared client locally so local builds need no package token.
RUN git clone https://github.com/wilddog64/rabbitmq-client-java.git /tmp/rabbitmq-client && \
    git -C /tmp/rabbitmq-client checkout "$RABBITMQ_CLIENT_COMMIT" && \
    mvn -B -f /tmp/rabbitmq-client/pom.xml package -DskipTests && \
    mvn install:install-file -B \
      -Dfile=/tmp/rabbitmq-client/rabbitmq-client/target/rabbitmq-client-1.0.1.jar \
      -DpomFile=/tmp/rabbitmq-client.pom && \
    mvn dependency:go-offline -B

# Copy source code
COPY src ./src

# Build the application
RUN mvn package -DskipTests -B

# Extract layers for optimized Docker image
RUN java -Djarmode=layertools -jar target/*.jar extract

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM eclipse-temurin:21-jre-alpine

# Security: Run as non-root user
RUN addgroup -g 1000 spring && \
    adduser -u 1000 -G spring -s /bin/sh -D spring

WORKDIR /app

# Copy extracted layers
COPY --from=builder /app/dependencies/ ./
COPY --from=builder /app/spring-boot-loader/ ./
COPY --from=builder /app/snapshot-dependencies/ ./
COPY --from=builder /app/application/ ./

# Set ownership
RUN chown -R spring:spring /app

USER spring:spring

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# JVM options for containers
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:InitialRAMPercentage=50.0"

# Run the application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
