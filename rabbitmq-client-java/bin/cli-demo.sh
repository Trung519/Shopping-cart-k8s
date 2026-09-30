#!/bin/bash
# CLI Demo - runs consumer and publisher together

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CLI_DIR="$PROJECT_DIR/rabbitmq-cli/target"

CONSUMER_JAR="$CLI_DIR/rabbitmq-cli-1.0.0-SNAPSHOT-consumer.jar"
PUBLISHER_JAR="$CLI_DIR/rabbitmq-cli-1.0.0-SNAPSHOT-publisher.jar"

echo "============================================================"
echo "  RabbitMQ CLI Demo"
echo "============================================================"
echo ""

# Check if JARs exist
if [[ ! -f "$CONSUMER_JAR" ]] || [[ ! -f "$PUBLISHER_JAR" ]]; then
    echo "Building CLI tools..."
    (cd "$PROJECT_DIR" && mvn package -DskipTests -q)
fi

echo "Starting consumer in background (will receive 3 messages)..."
java -jar "$CONSUMER_JAR" --count 3 > /tmp/consumer-output.txt 2>&1 &
CONSUMER_PID=$!

echo "Waiting for consumer to start..."
sleep 5

echo ""
echo "Publishing 3 test messages..."
echo "------------------------------------------------------------"

java -jar "$PUBLISHER_JAR" test.message '{"msg":"Hello 1"}' --quiet
java -jar "$PUBLISHER_JAR" test.message '{"msg":"Hello 2"}' --quiet
java -jar "$PUBLISHER_JAR" test.message '{"msg":"Hello 3"}' --quiet

echo "------------------------------------------------------------"
echo ""
echo "Waiting for messages to be received..."
sleep 3

echo ""
echo "Consumer received:"
grep -E '"(msg|message)"' /tmp/consumer-output.txt 2>/dev/null || echo "  (see /tmp/consumer-output.txt for details)"

# Cleanup
kill $CONSUMER_PID 2>/dev/null || true

echo ""
echo "============================================================"
echo "  CLI Demo Complete!"
echo "============================================================"
