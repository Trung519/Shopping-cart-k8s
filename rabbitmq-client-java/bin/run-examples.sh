#!/bin/bash
#
# Run example applications for the RabbitMQ Client Java library
#
# Usage:
#   ./bin/run-examples.sh publisher   # Run publisher example
#   ./bin/run-examples.sh consumer    # Run consumer example
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
    if [ ! -f "rabbitmq-examples/target/rabbitmq-examples-1.0.0-SNAPSHOT.jar" ]; then
        print_info "Examples not built. Building now..."
        mvn package -pl rabbitmq-examples -am -DskipTests -q
    fi
}

run_publisher() {
    print_header "Running Publisher Example"
    check_build

    print_info "Environment variables:"
    echo "  RABBITMQ_HOST=${RABBITMQ_HOST:-localhost}"
    echo "  RABBITMQ_PORT=${RABBITMQ_PORT:-5672}"
    echo "  VAULT_ADDR=${VAULT_ADDR:-http://localhost:8200}"
    echo ""

    cd rabbitmq-examples
    mvn spring-boot:run -Dspring-boot.run.main-class=com.shoppingcart.rabbitmq.examples.PublisherExample
}

run_consumer() {
    print_header "Running Consumer Example"
    check_build

    print_info "Environment variables:"
    echo "  RABBITMQ_HOST=${RABBITMQ_HOST:-localhost}"
    echo "  RABBITMQ_PORT=${RABBITMQ_PORT:-5672}"
    echo "  VAULT_ADDR=${VAULT_ADDR:-http://localhost:8200}"
    echo ""

    print_info "Press Ctrl+C to stop the consumer"
    echo ""

    cd rabbitmq-examples
    mvn spring-boot:run -Dspring-boot.run.main-class=com.shoppingcart.rabbitmq.examples.ConsumerExample
}

show_help() {
    echo "Usage: $0 <example>"
    echo ""
    echo "Examples:"
    echo "  publisher   Run the publisher example"
    echo "  consumer    Run the consumer example"
    echo "  help        Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  RABBITMQ_HOST      RabbitMQ host (default: localhost)"
    echo "  RABBITMQ_PORT      RabbitMQ port (default: 5672)"
    echo "  VAULT_ADDR         Vault address (default: http://localhost:8200)"
    echo "  VAULT_TOKEN        Vault token (required for Vault mode)"
    echo ""
    echo "Example:"
    echo "  RABBITMQ_HOST=rabbitmq.local ./bin/run-examples.sh publisher"
}

# Main
if [ $# -eq 0 ]; then
    print_error "No example specified"
    echo ""
    show_help
    exit 1
fi

case "$1" in
    publisher|pub)
        run_publisher
        ;;
    consumer|con)
        run_consumer
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown example: $1"
        show_help
        exit 1
        ;;
esac
