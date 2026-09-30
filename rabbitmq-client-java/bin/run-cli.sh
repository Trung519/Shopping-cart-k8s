#!/bin/bash
#
# Run CLI tools for the RabbitMQ Client Java library
#
# Usage:
#   ./bin/run-cli.sh publish <event-type> <json-payload>
#   ./bin/run-cli.sh consume <queue-name>
#
# Examples:
#   ./bin/run-cli.sh publish order.created '{"orderId":"123","amount":99.99}'
#   ./bin/run-cli.sh consume order-events
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

check_build() {
    if [ ! -f "rabbitmq-cli/target/rabbitmq-cli-1.0.0-SNAPSHOT.jar" ]; then
        print_info "CLI not built. Building now..."
        mvn package -pl rabbitmq-cli -am -DskipTests -q
    fi
}

run_publisher_cli() {
    if [ $# -lt 2 ]; then
        print_error "Usage: $0 publish <event-type> <json-payload>"
        echo ""
        echo "Example:"
        echo "  $0 publish order.created '{\"orderId\":\"123\"}'"
        exit 1
    fi

    EVENT_TYPE="$1"
    PAYLOAD="$2"
    shift 2

    print_header "Publishing Message"
    check_build

    print_info "Event Type: $EVENT_TYPE"
    print_info "Payload: $PAYLOAD"
    echo ""

    java -jar rabbitmq-cli/target/rabbitmq-cli-1.0.0-SNAPSHOT.jar \
        publish \
        --event-type "$EVENT_TYPE" \
        --payload "$PAYLOAD" \
        "$@"
}

run_consumer_cli() {
    if [ $# -lt 1 ]; then
        print_error "Usage: $0 consume <queue-name> [options]"
        echo ""
        echo "Example:"
        echo "  $0 consume order-events"
        echo "  $0 consume order-events --count 10"
        exit 1
    fi

    QUEUE="$1"
    shift

    print_header "Consuming Messages"
    check_build

    print_info "Queue: $QUEUE"
    print_info "Press Ctrl+C to stop"
    echo ""

    java -jar rabbitmq-cli/target/rabbitmq-cli-1.0.0-SNAPSHOT.jar \
        consume \
        --queue "$QUEUE" \
        "$@"
}

show_help() {
    echo "Usage: $0 <command> [args]"
    echo ""
    echo "Commands:"
    echo "  publish <event-type> <json-payload>   Publish a message"
    echo "  consume <queue-name>                  Consume messages from queue"
    echo "  help                                  Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  RABBITMQ_HOST      RabbitMQ host (default: localhost)"
    echo "  RABBITMQ_PORT      RabbitMQ port (default: 5672)"
    echo "  RABBITMQ_EXCHANGE  Exchange name (default: events)"
    echo "  VAULT_ADDR         Vault address (default: http://localhost:8200)"
    echo "  VAULT_TOKEN        Vault token (required for Vault mode)"
    echo ""
    echo "Examples:"
    echo "  # Publish a message"
    echo "  $0 publish order.created '{\"orderId\":\"123\",\"amount\":99.99}'"
    echo ""
    echo "  # Consume messages"
    echo "  $0 consume order-events"
    echo ""
    echo "  # Consume with count limit"
    echo "  $0 consume order-events --count 10"
    echo ""
    echo "  # Publish with custom exchange"
    echo "  RABBITMQ_EXCHANGE=notifications $0 publish email.sent '{\"to\":\"user@example.com\"}'"
}

# Main
if [ $# -eq 0 ]; then
    print_error "No command specified"
    echo ""
    show_help
    exit 1
fi

COMMAND="$1"
shift

case "$COMMAND" in
    publish|pub)
        run_publisher_cli "$@"
        ;;
    consume|con)
        run_consumer_cli "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
