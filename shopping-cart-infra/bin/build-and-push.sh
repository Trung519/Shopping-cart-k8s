#!/usr/bin/env bash
# Build and push container image to GitHub Container Registry (GHCR)
# Usage: ./scripts/build-and-push.sh <service-name> [tag] [--push]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

function print_success() { echo -e "${GREEN}✓ $1${NC}"; }
function print_error() { echo -e "${RED}✗ $1${NC}"; }
function print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Configuration
REGISTRY="ghcr.io"
SERVICE_NAME=""
TAG="test"
PUSH=false
PLATFORM="linux/amd64"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 <service-name> [tag] [--push] [--platform]"
            echo ""
            echo "Arguments:"
            echo "  service-name   Service to build (product-catalog, shopping-cart, order-service, payment-service)"
            echo "  tag            Image tag (default: test)"
            echo ""
            echo "Options:"
            echo "  --push         Push image to GHCR after building"
            echo "  --platform     Build platform (default: linux/amd64)"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 product-catalog                    # Build only, tag as 'test'"
            echo "  $0 product-catalog latest --push      # Build and push with 'latest' tag"
            echo "  $0 shopping-cart v1.0.0 --push        # Build and push with version tag"
            exit 0
            ;;
        *)
            if [ -z "$SERVICE_NAME" ]; then
                SERVICE_NAME="$1"
            else
                TAG="$1"
            fi
            shift
            ;;
    esac
done

# Validate service name
if [ -z "$SERVICE_NAME" ]; then
    print_error "Service name is required"
    echo "Usage: $0 <service-name> [tag] [--push]"
    echo "Run '$0 --help' for more information"
    exit 1
fi

# Valid services
VALID_SERVICES=("product-catalog" "shopping-cart" "order-service" "payment-service")
if [[ ! " ${VALID_SERVICES[@]} " =~ " ${SERVICE_NAME} " ]]; then
    print_error "Invalid service name: ${SERVICE_NAME}"
    echo "Valid services: ${VALID_SERVICES[*]}"
    exit 1
fi

print_header "Building Container Image"

# Get GitHub username
if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    USERNAME=$(gh api user -q .login)
    print_success "GitHub username: ${USERNAME}"
else
    print_error "GitHub CLI not authenticated"
    print_info "Please run: gh auth login"
    print_info "Or set GITHUB_USERNAME environment variable"
    if [ -z "${GITHUB_USERNAME:-}" ]; then
        exit 1
    fi
    USERNAME="${GITHUB_USERNAME}"
    print_info "Using GITHUB_USERNAME: ${USERNAME}"
fi

# Image name
IMAGE_NAME="${REGISTRY}/${USERNAME}/${SERVICE_NAME}:${TAG}"

print_info "Service: ${SERVICE_NAME}"
print_info "Tag: ${TAG}"
print_info "Image: ${IMAGE_NAME}"
print_info "Platform: ${PLATFORM}"

# Check if Dockerfile exists
DOCKERFILE="examples/dockerfiles/Dockerfile.${SERVICE_NAME}"
if [ ! -f "$DOCKERFILE" ]; then
    print_error "Dockerfile not found: ${DOCKERFILE}"
    print_info "Create the Dockerfile or use a service-specific repository"
    exit 1
fi

print_success "Dockerfile found: ${DOCKERFILE}"

# Create temporary build context
BUILD_CONTEXT="/tmp/shopping-cart-build-${SERVICE_NAME}"
print_info "Creating build context: ${BUILD_CONTEXT}"

rm -rf "${BUILD_CONTEXT}"
mkdir -p "${BUILD_CONTEXT}"

# Copy Dockerfile
cp "${DOCKERFILE}" "${BUILD_CONTEXT}/Dockerfile"

# Create sample application files based on service type
case "${SERVICE_NAME}" in
    product-catalog)
        print_info "Creating Node.js sample application..."
        cat > "${BUILD_CONTEXT}/package.json" << 'EOF'
{
  "name": "product-catalog",
  "version": "1.0.0",
  "description": "Shopping Cart Product Catalog Service",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}
EOF

        cat > "${BUILD_CONTEXT}/server.js" << 'EOF'
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.json({
    service: 'product-catalog',
    version: '1.0.0',
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(port, () => {
  console.log(`Product Catalog listening on port ${port}`);
});
EOF
        ;;

    shopping-cart)
        print_info "Creating Python sample application..."
        cat > "${BUILD_CONTEXT}/requirements.txt" << 'EOF'
flask==3.0.0
gunicorn==21.2.0
redis==5.0.1
EOF

        cat > "${BUILD_CONTEXT}/app.py" << 'EOF'
from flask import Flask, jsonify
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'service': 'shopping-cart',
        'version': '1.0.0',
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF
        ;;

    order-service)
        print_info "Creating Java sample application..."
        mkdir -p "${BUILD_CONTEXT}/src/main/java/com/shopping/order"

        cat > "${BUILD_CONTEXT}/pom.xml" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.shopping</groupId>
    <artifactId>order-service</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
EOF

        cat > "${BUILD_CONTEXT}/src/main/java/com/shopping/order/OrderServiceApplication.java" << 'EOF'
package com.shopping.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.HashMap;
import java.util.Map;
import java.time.Instant;

@SpringBootApplication
@RestController
public class OrderServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }

    @GetMapping("/")
    public Map<String, Object> home() {
        Map<String, Object> response = new HashMap<>();
        response.put("service", "order-service");
        response.put("version", "1.0.0");
        response.put("status", "healthy");
        response.put("timestamp", Instant.now().toString());
        return response;
    }
}
EOF
        ;;

    payment-service)
        print_info "Creating Go sample application..."
        mkdir -p "${BUILD_CONTEXT}/cmd/server"

        cat > "${BUILD_CONTEXT}/go.mod" << 'EOF'
module github.com/shopping-cart/payment-service

go 1.21

require github.com/gorilla/mux v1.8.1
EOF

        cat > "${BUILD_CONTEXT}/go.sum" << 'EOF'
github.com/gorilla/mux v1.8.1 h1:TuBL49tXwgrFYWhqrNgrUNEY92u81SPhu7sTdzQEiWY=
github.com/gorilla/mux v1.8.1/go.mod h1:AKf9I4AEqPTmMytcMc0KkNouC66V3BtZ4qD5fmWSiMQ=
EOF

        cat > "${BUILD_CONTEXT}/cmd/server/main.go" << 'EOF'
package main

import (
    "encoding/json"
    "log"
    "net/http"
    "time"
    "github.com/gorilla/mux"
)

type Response struct {
    Service   string    `json:"service"`
    Version   string    `json:"version"`
    Status    string    `json:"status"`
    Timestamp time.Time `json:"timestamp"`
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
    response := Response{
        Service:   "payment-service",
        Version:   "1.0.0",
        Status:    "healthy",
        Timestamp: time.Now().UTC(),
    }

    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func main() {
    r := mux.NewRouter()
    r.HandleFunc("/", homeHandler).Methods("GET")
    r.HandleFunc("/health", healthHandler).Methods("GET")

    log.Println("Payment Service listening on port 8081")
    log.Fatal(http.ListenAndServe(":8081", r))
}
EOF
        ;;
esac

# Create .dockerignore
cat > "${BUILD_CONTEXT}/.dockerignore" << 'EOF'
.git
.github
*.md
.env
.DS_Store
node_modules
target
*.log
EOF

print_success "Build context created"

# Build image
print_header "Building Docker Image"

if docker build --platform "${PLATFORM}" -t "${IMAGE_NAME}" "${BUILD_CONTEXT}"; then
    print_success "Image built successfully"
else
    print_error "Build failed"
    exit 1
fi

# Tag with git SHA if in git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    GIT_SHA=$(git rev-parse --short HEAD)
    SHA_TAG="${REGISTRY}/${USERNAME}/${SERVICE_NAME}:${GIT_SHA}"

    print_info "Tagging with git SHA: ${GIT_SHA}"
    docker tag "${IMAGE_NAME}" "${SHA_TAG}"
    print_success "Tagged: ${SHA_TAG}"
fi

# Tag with latest if tag is a version
if [[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    LATEST_TAG="${REGISTRY}/${USERNAME}/${SERVICE_NAME}:latest"
    print_info "Tagging as latest"
    docker tag "${IMAGE_NAME}" "${LATEST_TAG}"
    print_success "Tagged: ${LATEST_TAG}"
fi

# Show image info
print_header "Image Information"
docker images "${REGISTRY}/${USERNAME}/${SERVICE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

# Test image locally
print_header "Testing Image"

CONTAINER_NAME="test-${SERVICE_NAME}-${RANDOM}"

# Determine port based on service
case "${SERVICE_NAME}" in
    product-catalog) PORT=3000 ;;
    shopping-cart) PORT=5000 ;;
    order-service) PORT=8080 ;;
    payment-service) PORT=8081 ;;
esac

print_info "Starting test container..."
if docker run -d --name "${CONTAINER_NAME}" -p "${PORT}:${PORT}" "${IMAGE_NAME}"; then
    print_success "Container started: ${CONTAINER_NAME}"

    # Wait for container to be ready
    sleep 5

    # Test endpoint
    print_info "Testing endpoint: http://localhost:${PORT}"
    if curl -f -s "http://localhost:${PORT}" > /dev/null; then
        print_success "Health check passed"
        curl -s "http://localhost:${PORT}" | jq .
    else
        print_error "Health check failed"
        docker logs "${CONTAINER_NAME}"
    fi

    # Cleanup test container
    print_info "Cleaning up test container..."
    docker stop "${CONTAINER_NAME}" > /dev/null
    docker rm "${CONTAINER_NAME}" > /dev/null
    print_success "Test container removed"
else
    print_error "Failed to start container"
    exit 1
fi

# Push to GHCR if requested
if [ "$PUSH" = true ]; then
    print_header "Pushing to GitHub Container Registry"

    # Check authentication
    if ! docker info 2>&1 | grep -q "Username:"; then
        print_info "Logging in to GHCR..."

        if [ -z "${GITHUB_TOKEN:-}" ]; then
            if command -v gh &> /dev/null && gh auth status &> /dev/null; then
                export GITHUB_TOKEN=$(gh auth token)
            else
                print_error "GITHUB_TOKEN not set and gh not authenticated"
                print_info "Run: gh auth login"
                print_info "Or: export GITHUB_TOKEN=ghp_xxxx"
                exit 1
            fi
        fi

        echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${USERNAME}" --password-stdin
        print_success "Logged in to GHCR"
    fi

    # Push all tags
    print_info "Pushing ${IMAGE_NAME}..."
    docker push "${IMAGE_NAME}"
    print_success "Pushed: ${IMAGE_NAME}"

    if git rev-parse --git-dir > /dev/null 2>&1; then
        print_info "Pushing ${SHA_TAG}..."
        docker push "${SHA_TAG}"
        print_success "Pushed: ${SHA_TAG}"
    fi

    if [[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_info "Pushing ${LATEST_TAG}..."
        docker push "${LATEST_TAG}"
        print_success "Pushed: ${LATEST_TAG}"
    fi

    print_header "Push Complete"
    print_success "Images available at: https://github.com/${USERNAME}?tab=packages"
    print_info "View package: https://github.com/users/${USERNAME}/packages/container/${SERVICE_NAME}"
else
    print_header "Build Complete"
    print_info "To push to GHCR, run with --push flag:"
    echo "  $0 ${SERVICE_NAME} ${TAG} --push"
fi

# Cleanup build context
rm -rf "${BUILD_CONTEXT}"
print_info "Build context cleaned up"

print_success "Done!"
