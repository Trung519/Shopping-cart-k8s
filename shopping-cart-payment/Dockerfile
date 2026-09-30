# Payment Service Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Build
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /app

# Install Maven (wrapper incompatible with Alpine)
RUN apk add --no-cache git maven

ARG RABBITMQ_CLIENT_COMMIT=72412443e2dddb96c714488b0f796146e9e55036

# Copy build descriptors and resolve dependencies (cached layer)
COPY pom.xml checkstyle.xml ./
COPY vendor/rabbitmq-client-1.0.1.pom /tmp/rabbitmq-client.pom
RUN git clone https://github.com/wilddog64/rabbitmq-client-java.git /tmp/rabbitmq-client && \
    git -C /tmp/rabbitmq-client checkout "$RABBITMQ_CLIENT_COMMIT" && \
    mvn -B -f /tmp/rabbitmq-client/pom.xml package -DskipTests && \
    mvn install:install-file -B \
      -Dfile=/tmp/rabbitmq-client/rabbitmq-client/target/rabbitmq-client-1.0.1.jar \
      -DpomFile=/tmp/rabbitmq-client.pom && \
    mvn dependency:go-offline -B

# Copy source code
COPY src/ src/

# Build the application
RUN mvn package -DskipTests -B

# Extract layers for optimized Docker layering
RUN java -Djarmode=layertools -jar target/*.jar extract --destination extracted

# Stage 2: Runtime
FROM eclipse-temurin:21-jre-alpine AS runtime

# Security: Run as non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

WORKDIR /app

# Copy extracted layers (better caching)
COPY --from=builder /app/extracted/dependencies/ ./
COPY --from=builder /app/extracted/spring-boot-loader/ ./
COPY --from=builder /app/extracted/snapshot-dependencies/ ./
COPY --from=builder /app/extracted/application/ ./

# Set ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8084

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8084/actuator/health/liveness || exit 1

# JVM options for containers
ENV JAVA_OPTS="-XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=75.0 \
    -XX:InitialRAMPercentage=50.0 \
    -Djava.security.egd=file:/dev/./urandom \
    -Dspring.profiles.active=default"

# Run the application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS org.springframework.boot.loader.launch.JarLauncher"]
