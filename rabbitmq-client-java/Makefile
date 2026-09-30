# RabbitMQ Client Java - Makefile
#
# Usage:
#   make help       Show available targets
#   make build      Build the project
#   make test       Run unit tests
#   make package    Build JAR packages
#

.PHONY: help build clean compile package install test test-unit test-int test-all coverage \
        demo run-publisher run-consumer cli-demo cli-publish cli-consume cli \
        dev-setup dev-start dev-stop dev-logs \
        lint format check docs

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

#------------------------------------------------------------------------------
# Help
#------------------------------------------------------------------------------

help: ## Show this help message
	@echo "$(GREEN)RabbitMQ Client Java$(NC)"
	@echo ""
	@echo "$(BLUE)Usage:$(NC) make [target]"
	@echo ""
	@echo "$(BLUE)Build Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(build|clean|compile|package|install)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Test Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(test|coverage)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Run Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(^demo:|run-|cli-)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Development Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(dev-)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Quality Targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(lint|format|check|docs)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

#------------------------------------------------------------------------------
# Build Targets
#------------------------------------------------------------------------------

build: compile ## Build the project (alias for compile)

compile: ## Compile all modules
	mvn compile

clean: ## Clean build artifacts
	mvn clean

package: ## Build JAR packages (skip tests)
	mvn package -DskipTests

install: ## Install to local Maven repository
	mvn install -DskipTests

full-build: ## Full build with tests
	mvn verify

quick: ## Quick build (skip tests, skip javadoc)
	mvn package -DskipTests -Dmaven.javadoc.skip=true

#------------------------------------------------------------------------------
# Test Targets
#------------------------------------------------------------------------------

test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests only
	mvn test -pl rabbitmq-client -DskipITs

test-int: ## Run integration tests (requires Docker)
	mvn verify -pl rabbitmq-client -DskipUTs -Pintegration

test-all: ## Run all tests
	mvn verify -pl rabbitmq-client

coverage: ## Generate test coverage report
	mvn verify -pl rabbitmq-client -Pcoverage
	@echo ""
	@echo "Coverage report: rabbitmq-client/target/site/jacoco/index.html"

#------------------------------------------------------------------------------
# Run Examples
#------------------------------------------------------------------------------

demo: install ## Run combined publisher+consumer demo (recommended)
	cd rabbitmq-examples && mvn spring-boot:run -Dspring-boot.run.main-class=com.shoppingcart.rabbitmq.examples.DemoExample -Dspring-boot.run.profiles=demo

run-publisher: install ## Run publisher example (standalone)
	cd rabbitmq-examples && mvn spring-boot:run -Dspring-boot.run.main-class=com.shoppingcart.rabbitmq.examples.PublisherExample -Dspring-boot.run.profiles=demo

run-consumer: install ## Run consumer example (standalone, waits indefinitely)
	cd rabbitmq-examples && mvn spring-boot:run -Dspring-boot.run.main-class=com.shoppingcart.rabbitmq.examples.ConsumerExample -Dspring-boot.run.profiles=demo

#------------------------------------------------------------------------------
# CLI Tools
#------------------------------------------------------------------------------

CLI_DIR := $(shell pwd)/rabbitmq-cli/target
CLI_CONSUMER_JAR := $(CLI_DIR)/rabbitmq-cli-1.0.0-SNAPSHOT-consumer.jar
CLI_PUBLISHER_JAR := $(CLI_DIR)/rabbitmq-cli-1.0.0-SNAPSHOT-publisher.jar

cli-demo: package ## Run CLI demo (publish + consume in one command)
	@./bin/cli-demo.sh

cli: ## Show CLI usage
	@echo "CLI Tools - Publisher and Consumer"
	@echo ""
	@echo "Quick Demo (recommended):"
	@echo "  make cli-demo"
	@echo ""
	@echo "Standalone commands:"
	@echo "  make cli-consume [QUEUE=name] [EXCHANGE=name]"
	@echo "  make cli-publish [EVENT=type] [PAYLOAD=json] [COUNT=n]"

cli-consume: package ## Start consumer: make cli-consume [QUEUE=name]
	java -jar "$(CLI_CONSUMER_JAR)" $(if $(QUEUE),--queue $(QUEUE)) $(if $(EXCHANGE),--exchange $(EXCHANGE))

cli-publish: package ## Publish messages: make cli-publish [EVENT=type] [PAYLOAD=json]
	java -jar "$(CLI_PUBLISHER_JAR)" $(if $(EVENT),$(EVENT),test.event) $(if $(PAYLOAD),'$(PAYLOAD)',) $(if $(COUNT),-n $(COUNT)) $(if $(EXCHANGE),--exchange $(EXCHANGE))

#------------------------------------------------------------------------------
# Development Environment
#------------------------------------------------------------------------------

DOCKER_COMPOSE := docker compose

dev-setup: ## Set up development environment (start services, configure Vault)
	@./bin/setup-dev.sh

dev-start: ## Start RabbitMQ and Vault containers
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "RabbitMQ: http://localhost:15672 (guest/guest)"
	@echo "Vault:    http://localhost:8200 (token: root)"

dev-stop: ## Stop development containers
	$(DOCKER_COMPOSE) down

dev-logs: ## Show container logs
	$(DOCKER_COMPOSE) logs -f

dev-status: ## Show container status
	$(DOCKER_COMPOSE) ps

dev-clean: ## Stop and remove containers and volumes
	$(DOCKER_COMPOSE) down -v

#------------------------------------------------------------------------------
# Code Quality
#------------------------------------------------------------------------------

lint: ## Run static analysis (checkstyle, spotbugs)
	mvn checkstyle:check spotbugs:check

format: ## Format code with spotless
	mvn spotless:apply

format-check: ## Check code formatting
	mvn spotless:check

check: ## Run all quality checks
	mvn verify -DskipTests

docs: ## Generate Javadoc
	mvn javadoc:aggregate
	@echo ""
	@echo "Javadoc: target/site/apidocs/index.html"

#------------------------------------------------------------------------------
# Utility
#------------------------------------------------------------------------------

version: ## Show project version
	@mvn help:evaluate -Dexpression=project.version -q -DforceStdout

deps: ## Show dependency tree
	mvn dependency:tree

deps-updates: ## Check for dependency updates
	mvn versions:display-dependency-updates

tree: ## Show module structure
	@echo "$(GREEN)Project Structure:$(NC)"
	@echo "rabbitmq-client-java (parent)"
	@echo "├── rabbitmq-client    - Core library"
	@echo "├── rabbitmq-cli       - CLI tools"
	@echo "└── rabbitmq-examples  - Example applications"
