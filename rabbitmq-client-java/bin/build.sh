#!/bin/bash
#
# Build the RabbitMQ Client Java library
#
# Usage:
#   ./bin/build.sh              # Build all modules
#   ./bin/build.sh clean        # Clean and build
#   ./bin/build.sh package      # Build JAR packages
#   ./bin/build.sh install      # Install to local Maven repo
#   ./bin/build.sh quick        # Quick build (skip tests)
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

check_java() {
    print_info "Checking Java version..."
    if ! command -v java &> /dev/null; then
        print_error "Java not found. Please install Java 21 or higher."
        exit 1
    fi

    JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f2 | cut -d'.' -f1)
    if [ "$JAVA_VERSION" -lt 21 ]; then
        print_warning "Java 21+ recommended. Found version: $JAVA_VERSION"
    else
        print_info "Java version: $JAVA_VERSION"
    fi
}

check_maven() {
    print_info "Checking Maven..."
    if ! command -v mvn &> /dev/null; then
        print_error "Maven not found. Please install Maven 3.9+."
        exit 1
    fi
    MVN_VERSION=$(mvn -version | head -n 1)
    print_info "$MVN_VERSION"
}

build_compile() {
    print_header "Compiling Project"
    mvn compile
}

build_clean() {
    print_header "Cleaning and Building Project"
    mvn clean compile
}

build_package() {
    print_header "Building JAR Packages"
    mvn package -DskipTests

    echo ""
    print_info "JAR files created:"
    find . -name "*.jar" -path "*/target/*" -type f | while read jar; do
        echo "  $jar"
    done
}

build_install() {
    print_header "Installing to Local Maven Repository"
    mvn install -DskipTests

    echo ""
    print_info "Installed artifacts:"
    echo "  com.shoppingcart:rabbitmq-client"
    echo "  com.shoppingcart:rabbitmq-cli"
    echo "  com.shoppingcart:rabbitmq-examples"
}

build_quick() {
    print_header "Quick Build (Skip Tests)"
    mvn package -DskipTests -Dmaven.javadoc.skip=true
}

build_full() {
    print_header "Full Build with Tests"
    mvn verify
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  compile   Compile the project (default)"
    echo "  clean     Clean and compile"
    echo "  package   Build JAR packages (skip tests)"
    echo "  install   Install to local Maven repository"
    echo "  quick     Quick build (skip tests, skip javadoc)"
    echo "  full      Full build with all tests"
    echo "  help      Show this help message"
    echo ""
    echo "If no command is specified, runs compile."
}

# Main
check_java
check_maven
echo ""

case "${1:-compile}" in
    compile)
        build_compile
        ;;
    clean)
        build_clean
        ;;
    package|pkg)
        build_package
        ;;
    install)
        build_install
        ;;
    quick)
        build_quick
        ;;
    full)
        build_full
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
print_header "Build completed successfully!"
