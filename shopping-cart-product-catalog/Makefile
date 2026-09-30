# Shopping Cart Product Catalog Service - Makefile
# Python 3.11+ / FastAPI

.PHONY: help install install-dev run run-dev test test-unit test-integration test-security test-cov lint format check clean docker-build docker-run k8s-build k8s-deploy k8s-delete k8s-status k8s-logs k8s-describe k8s-restart k8s-port-forward k8s-shell argocd-status argocd-sync argocd-refresh argocd-diff argocd-history

# Default target
.DEFAULT_GOAL := help

# Python settings
PYTHON := python3
PIP := pip3
VENV := .venv
VENV_BIN := $(VENV)/bin
DOCKER_IMAGE := shopping-cart-product-catalog
DOCKER_TAG ?= v1.1.0

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n${BLUE}Usage:${NC}\n  make ${GREEN}<target>${NC}\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  ${GREEN}%-20s${NC} %s\n", $$1, $$2 } /^##@/ { printf "\n${YELLOW}%s${NC}\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup

venv: ## Create virtual environment
	@echo "${BLUE}Creating virtual environment...${NC}"
	$(PYTHON) -m venv $(VENV)
	@echo "${GREEN}Virtual environment created. Activate with: source $(VENV)/bin/activate${NC}"

install: ## Install production dependencies
	@echo "${BLUE}Installing dependencies...${NC}"
	$(PIP) install -e .
	@echo "${GREEN}Dependencies installed${NC}"

install-dev: ## Install development dependencies
	@echo "${BLUE}Installing dev dependencies...${NC}"
	$(PIP) install -e ".[dev,rabbitmq]"
	@echo "${GREEN}Dev dependencies installed${NC}"

install-rabbitmq: ## Install RabbitMQ client library
	@echo "${BLUE}Installing RabbitMQ client...${NC}"
	$(PIP) install -e "../rabbitmq-client-python/python" || echo "${YELLOW}RabbitMQ client not found locally${NC}"

install-all: install-dev install-rabbitmq ## Install all dependencies including RabbitMQ

##@ Development

run: ## Run the application
	@echo "${BLUE}Starting Product Catalog Service...${NC}"
	$(PYTHON) -m product_catalog.main

run-dev: ## Run with auto-reload
	@echo "${BLUE}Starting Product Catalog Service (dev mode)...${NC}"
	uvicorn product_catalog.main:app --reload --host 0.0.0.0 --port 8000

run-debug: ## Run with debug logging
	@echo "${BLUE}Starting with debug logging...${NC}"
	LOG_LEVEL=DEBUG uvicorn product_catalog.main:app --reload --host 0.0.0.0 --port 8000

shell: ## Open Python shell with app context
	@echo "${BLUE}Opening Python shell...${NC}"
	$(PYTHON) -c "from product_catalog.main import app; from product_catalog.config import get_settings; import code; code.interact(local=locals())"

##@ Testing

test: ## Run all tests
	@echo "${BLUE}Running all tests...${NC}"
	pytest tests/ -v

test-unit: ## Run unit tests only
	@echo "${BLUE}Running unit tests...${NC}"
	pytest tests/unit/ -v

test-integration: ## Run integration tests only
	@echo "${BLUE}Running integration tests...${NC}"
	pytest tests/integration/ -v

test-security: ## Run security tests only
	@echo "${BLUE}Running security tests...${NC}"
	pytest tests/unit/test_security*.py -v

test-cov: ## Run tests with coverage
	@echo "${BLUE}Running tests with coverage...${NC}"
	pytest tests/ --cov=product_catalog --cov-report=html --cov-report=term-missing
	@echo "${GREEN}Coverage report: htmlcov/index.html${NC}"

test-cov-xml: ## Run tests with coverage (XML for CI)
	@echo "${BLUE}Running tests with XML coverage...${NC}"
	pytest tests/ --cov=product_catalog --cov-report=xml

test-watch: ## Run tests in watch mode
	@echo "${BLUE}Running tests in watch mode...${NC}"
	ptw tests/ -- -v

test-failed: ## Re-run failed tests
	@echo "${BLUE}Re-running failed tests...${NC}"
	pytest tests/ --lf -v

##@ Code Quality

lint: ## Run linter (ruff)
	@echo "${BLUE}Running linter...${NC}"
	ruff check src/ tests/

lint-fix: ## Fix linting issues
	@echo "${BLUE}Fixing linting issues...${NC}"
	ruff check src/ tests/ --fix

format: ## Format code (black + isort)
	@echo "${BLUE}Formatting code...${NC}"
	black src/ tests/
	isort src/ tests/

format-check: ## Check code formatting
	@echo "${BLUE}Checking code format...${NC}"
	black --check src/ tests/
	isort --check-only src/ tests/

typecheck: ## Run type checker (mypy)
	@echo "${BLUE}Running type checker...${NC}"
	mypy src/

check: lint typecheck test ## Run all checks (lint + typecheck + test)

check-all: format-check lint typecheck test-cov ## Run all checks including format

##@ Security

security-scan: ## Run security scan (bandit)
	@echo "${BLUE}Running security scan...${NC}"
	bandit -r src/ -ll || echo "${YELLOW}Bandit not installed: pip install bandit${NC}"

deps-audit: ## Audit dependencies for vulnerabilities
	@echo "${BLUE}Auditing dependencies...${NC}"
	pip-audit || echo "${YELLOW}pip-audit not installed: pip install pip-audit${NC}"

##@ Build & Package

build: ## Build package
	@echo "${BLUE}Building package...${NC}"
	$(PYTHON) -m build
	@echo "${GREEN}Package built in dist/${NC}"

clean: ## Clean build artifacts
	@echo "${BLUE}Cleaning build artifacts...${NC}"
	rm -rf build/ dist/ *.egg-info .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "${GREEN}Cleaned${NC}"

##@ Docker

docker-build: ## Build Docker image
	@echo "${BLUE}Building Docker image...${NC}"
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "${GREEN}Image built: $(DOCKER_IMAGE):$(DOCKER_TAG)${NC}"

docker-run: ## Run Docker container
	@echo "${BLUE}Running Docker container...${NC}"
	docker run --rm -p 8000:8000 \
		-e DB_HOST=host.docker.internal \
		-e RABBITMQ_HOST=host.docker.internal \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

docker-push: ## Push Docker image to registry
	@echo "${BLUE}Pushing Docker image...${NC}"
	docker push $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-compose-up: ## Start with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop docker-compose
	docker-compose down

##@ Database

db-migrate: ## Run database migrations (Alembic)
	@echo "${BLUE}Running database migrations...${NC}"
	alembic upgrade head

db-migrate-create: ## Create new migration
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-downgrade: ## Rollback last migration
	@echo "${BLUE}Rolling back last migration...${NC}"
	alembic downgrade -1

db-history: ## Show migration history
	alembic history

db-current: ## Show current migration
	alembic current

##@ Documentation

docs: ## Generate API documentation
	@echo "${BLUE}Generating documentation...${NC}"
	pdoc --html --output-dir docs/api src/product_catalog || echo "${YELLOW}pdoc not installed${NC}"

docs-serve: ## Serve API docs locally
	@echo "${BLUE}Serving docs at http://localhost:8080${NC}"
	$(PYTHON) -m http.server 8080 --directory docs/api

openapi: ## Export OpenAPI schema
	@echo "${BLUE}Exporting OpenAPI schema...${NC}"
	$(PYTHON) -c "from product_catalog.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > openapi.json
	@echo "${GREEN}OpenAPI schema: openapi.json${NC}"

##@ Dependencies

deps: ## Show installed dependencies
	@echo "${BLUE}Installed dependencies:${NC}"
	$(PIP) list

deps-tree: ## Show dependency tree
	@echo "${BLUE}Dependency tree:${NC}"
	pipdeptree || echo "${YELLOW}pipdeptree not installed: pip install pipdeptree${NC}"

deps-outdated: ## Check for outdated dependencies
	@echo "${BLUE}Checking for outdated dependencies...${NC}"
	$(PIP) list --outdated

deps-update: ## Update all dependencies
	@echo "${BLUE}Updating dependencies...${NC}"
	$(PIP) install --upgrade -e ".[dev,rabbitmq]"

freeze: ## Export requirements.txt
	@echo "${BLUE}Exporting requirements...${NC}"
	$(PIP) freeze > requirements.lock.txt
	@echo "${GREEN}Requirements exported to requirements.lock.txt${NC}"

##@ Utilities

version: ## Show package version
	@$(PYTHON) -c "from product_catalog import __version__; print(__version__)"

info: ## Show environment info
	@echo "${BLUE}Environment Info:${NC}"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Pip: $$($(PIP) --version)"
	@echo "Virtual Env: $(VENV)"

tree: ## Show project structure
	@tree -I '__pycache__|.venv|.git|*.egg-info|htmlcov|.pytest_cache' -L 3

loc: ## Count lines of code
	@echo "${BLUE}Lines of code:${NC}"
	@find src -name "*.py" | xargs wc -l | tail -1

health: ## Check service health (requires running service)
	@echo "${BLUE}Checking service health...${NC}"
	curl -s http://localhost:8000/health | python3 -m json.tool

##@ Kubernetes

k8s-build: docker-build ## Build and tag for Kubernetes
	@echo "${BLUE}Tagging image for k3s...${NC}"
	docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) localhost:5000/$(DOCKER_IMAGE):$(DOCKER_TAG) 2>/dev/null || true

k8s-deploy: ## Deploy to Kubernetes (k3s)
	@echo "${BLUE}Deploying to Kubernetes...${NC}"
	helm upgrade --install product-catalog helmchart --namespace shopping-cart-apps -f ../config-secret-secure/values/local/22-product-catalog.yaml
	@echo "${GREEN}Deployment complete${NC}"

k8s-delete: ## Delete from Kubernetes
	@echo "${YELLOW}Deleting from Kubernetes...${NC}"
	helm uninstall product-catalog --namespace shopping-cart-apps --ignore-not-found
	@echo "${GREEN}Resources deleted${NC}"

k8s-status: ## Show deployment status
	@echo "${BLUE}Deployment status:${NC}"
	kubectl get pods,svc,hpa -n shopping-cart-apps -l app.kubernetes.io/name=product-catalog

k8s-logs: ## Show pod logs
	@echo "${BLUE}Pod logs:${NC}"
	kubectl logs -n shopping-cart-apps -l app.kubernetes.io/name=product-catalog --tail=100 -f

k8s-describe: ## Describe deployment
	kubectl describe deployment product-catalog -n shopping-cart-apps

k8s-restart: ## Restart deployment
	@echo "${BLUE}Restarting deployment...${NC}"
	kubectl rollout restart deployment/product-catalog -n shopping-cart-apps

k8s-port-forward: ## Port forward to local (8080)
	@echo "${BLUE}Port forwarding to localhost:8080...${NC}"
	kubectl port-forward -n shopping-cart-apps svc/product-catalog 8080:80

k8s-shell: ## Open shell in pod
	@echo "${BLUE}Opening shell in pod...${NC}"
	kubectl exec -n shopping-cart-apps -it $$(kubectl get pods -n shopping-cart-apps -l app.kubernetes.io/name=product-catalog -o jsonpath='{.items[0].metadata.name}') -- /bin/sh

##@ ArgoCD

argocd-status: ## Show ArgoCD application status
	@echo "${BLUE}ArgoCD Application Status:${NC}"
	@kubectl get application product-catalog -n argocd -o wide 2>/dev/null || echo "Application not found in ArgoCD"

argocd-sync: ## Trigger ArgoCD sync
	@echo "${BLUE}Triggering ArgoCD sync...${NC}"
	@argocd app sync product-catalog 2>/dev/null || \
		kubectl patch application product-catalog -n argocd --type merge \
		-p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{}}}' 2>/dev/null || \
		echo "ArgoCD CLI not available and kubectl patch failed"
	@echo "${GREEN}Sync triggered${NC}"

argocd-refresh: ## Refresh ArgoCD application (fetch latest from Git)
	@echo "${BLUE}Refreshing ArgoCD application...${NC}"
	@argocd app get product-catalog --refresh 2>/dev/null || \
		kubectl patch application product-catalog -n argocd --type merge \
		-p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"normal"}}}' 2>/dev/null || \
		echo "Refresh failed"

argocd-diff: ## Show ArgoCD diff (what would change)
	@echo "${BLUE}ArgoCD Diff:${NC}"
	@argocd app diff product-catalog 2>/dev/null || echo "ArgoCD CLI required for diff"

argocd-history: ## Show ArgoCD deployment history
	@echo "${BLUE}Deployment History:${NC}"
	@argocd app history product-catalog 2>/dev/null || \
		kubectl get application product-catalog -n argocd -o jsonpath='{.status.history}' | jq . 2>/dev/null || \
		echo "No history available"

##@ Production

prod-run: ## Run in production mode
	@echo "${BLUE}Running in production mode...${NC}"
	ENVIRONMENT=production uvicorn product_catalog.main:app --host 0.0.0.0 --port 8000 --workers 4

prod-gunicorn: ## Run with Gunicorn
	@echo "${BLUE}Running with Gunicorn...${NC}"
	gunicorn product_catalog.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
