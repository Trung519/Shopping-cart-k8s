#!/bin/bash
#
# Run tests for the RabbitMQ Client Java library
#
# Usage:
#   ./bin/run-tests.sh           # Run all unit tests
#   ./bin/run-tests.sh unit      # Run unit tests only
#   ./bin/run-tests.sh int       # Run integration tests only
#   ./bin/run-tests.sh all       # Run all tests with coverage
#   ./bin/run-tests.sh coverage  # Generate coverage report
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

run_unit_tests() {
    print_header "Running Unit Tests"
    mvn test -pl rabbitmq-client -DskipITs
}

run_integration_tests() {
    print_header "Running Integration Tests"

    # Check if Docker is available for Testcontainers
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found. Integration tests require Docker for Testcontainers."
        exit 1
    fi

    mvn verify -pl rabbitmq-client -DskipUTs -Pintegration
}

run_all_tests() {
    print_header "Running All Tests"
    mvn verify -pl rabbitmq-client
}

generate_coverage() {
    print_header "Generating Coverage Report"
    mvn verify -pl rabbitmq-client -Pcoverage

    echo ""
    echo -e "${GREEN}Coverage report generated at:${NC}"
    echo "  rabbitmq-client/target/site/jacoco/index.html"
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  unit      Run unit tests only"
    echo "  int       Run integration tests only (requires Docker)"
    echo "  all       Run all tests"
    echo "  coverage  Run tests with coverage report"
    echo "  help      Show this help message"
    echo ""
    echo "If no command is specified, runs unit tests."
}

# Main
case "${1:-unit}" in
    unit)
        run_unit_tests
        ;;
    int|integration)
        run_integration_tests
        ;;
    all)
        run_all_tests
        ;;
    coverage)
        generate_coverage
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

echo ""
print_header "Tests completed successfully!"
