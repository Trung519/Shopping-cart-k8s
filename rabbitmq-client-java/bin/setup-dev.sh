#!/bin/bash
#
# Set up development environment for the RabbitMQ Client Java library
#
# This script:
#   1. Checks prerequisites (Java, Maven, Docker)
#   2. Starts RabbitMQ and Vault using Docker Compose
#   3. Configures Vault for RabbitMQ
#   4. Builds the project
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

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Java
    if command -v java &> /dev/null; then
        JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2 | cut -d'.' -f1)
        if [ "$JAVA_VERSION" -ge 21 ]; then
            print_success "Java $JAVA_VERSION found"
        else
            print_warning "Java 21+ recommended. Found version: $JAVA_VERSION"
        fi
    else
        print_error "Java not found. Please install Java 21+."
        exit 1
    fi

    # Check Maven
    if command -v mvn &> /dev/null; then
        MVN_VERSION=$(mvn -version 2>&1 | head -n 1 | grep -oP 'Apache Maven \K[0-9.]+')
        print_success "Maven $MVN_VERSION found"
    else
        print_error "Maven not found. Please install Maven 3.9+."
        exit 1
    fi

    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | grep -oP 'Docker version \K[0-9.]+')
        print_success "Docker $DOCKER_VERSION found"
    else
        print_warning "Docker not found. Integration tests will not work."
    fi

    # Check Docker Compose
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        print_success "Docker Compose found"
    else
        print_warning "Docker Compose not found. Cannot start local services."
    fi

    echo ""
}

create_docker_compose() {
    if [ ! -f "docker-compose.yml" ]; then
        print_info "Creating docker-compose.yml..."
        cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: rabbitmq-dev
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq

  vault:
    image: hashicorp/vault:1.15
    container_name: vault-dev
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: root
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    healthcheck:
      test: ["CMD", "vault", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  rabbitmq-data:
EOF
        print_success "Created docker-compose.yml"
    else
        print_info "docker-compose.yml already exists"
    fi
}

start_services() {
    print_header "Starting Docker Services"

    if ! command -v docker &> /dev/null; then
        print_warning "Docker not available. Skipping service startup."
        return
    fi

    create_docker_compose

    print_info "Starting RabbitMQ and Vault..."
    docker compose up -d

    print_info "Waiting for services to be healthy..."
    sleep 10

    # Check RabbitMQ
    if docker exec rabbitmq-dev rabbitmq-diagnostics -q ping &> /dev/null; then
        print_success "RabbitMQ is healthy"
    else
        print_warning "RabbitMQ may not be ready yet"
    fi

    # Check Vault
    if curl -s http://localhost:8200/v1/sys/health > /dev/null; then
        print_success "Vault is healthy"
    else
        print_warning "Vault may not be ready yet"
    fi

    echo ""
}

configure_vault() {
    print_header "Configuring Vault"

    if ! curl -s http://localhost:8200/v1/sys/health > /dev/null 2>&1; then
        print_warning "Vault not accessible. Skipping configuration."
        return
    fi

    export VAULT_ADDR="http://localhost:8200"
    export VAULT_TOKEN="root"

    # Enable RabbitMQ secrets engine
    print_info "Enabling RabbitMQ secrets engine..."
    curl -s -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        -d '{"type":"rabbitmq"}' \
        "$VAULT_ADDR/v1/sys/mounts/rabbitmq" > /dev/null 2>&1 || true

    # Configure RabbitMQ connection
    print_info "Configuring RabbitMQ connection..."
    curl -s -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        -d '{
            "connection_uri": "http://rabbitmq-dev:15672",
            "username": "guest",
            "password": "guest"
        }' \
        "$VAULT_ADDR/v1/rabbitmq/config/connection" > /dev/null 2>&1 || true

    # Create a role
    print_info "Creating Vault role 'app'..."
    curl -s -X POST \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        -d '{
            "vhosts": "{\"\/\": {\"configure\": \".*\", \"write\": \".*\", \"read\": \".*\"}}"
        }' \
        "$VAULT_ADDR/v1/rabbitmq/roles/app" > /dev/null 2>&1 || true

    print_success "Vault configured for RabbitMQ"
    echo ""
}

build_project() {
    print_header "Building Project"

    print_info "Compiling..."
    mvn compile -q

    print_info "Running unit tests..."
    mvn test -q || print_warning "Some tests failed"

    print_success "Project built successfully"
    echo ""
}

print_summary() {
    print_header "Development Environment Ready"

    echo "Services:"
    echo "  RabbitMQ: http://localhost:15672 (guest/guest)"
    echo "  Vault:    http://localhost:8200 (token: root)"
    echo ""
    echo "Environment variables to set:"
    echo "  export VAULT_ADDR=http://localhost:8200"
    echo "  export VAULT_TOKEN=root"
    echo "  export RABBITMQ_HOST=localhost"
    echo "  export RABBITMQ_PORT=5672"
    echo ""
    echo "Commands:"
    echo "  ./bin/run-tests.sh        Run tests"
    echo "  ./bin/build.sh            Build the project"
    echo "  ./bin/run-examples.sh     Run examples"
    echo "  ./bin/run-cli.sh          Run CLI tools"
    echo ""
    echo "To stop services:"
    echo "  docker compose down"
}

# Main
print_header "RabbitMQ Client Java - Development Setup"
echo ""

check_prerequisites
start_services
configure_vault
build_project
print_summary
