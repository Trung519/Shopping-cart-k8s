# Product Catalog Service — Testing Guide

## Overview
Testing uses pytest for unit coverage, mypy for types, and pip-audit for dependency scanning. The service also exposes FastAPI test clients for integration-style checks.

## Unit Tests
```bash
# Run pytest suite
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=term-missing
```
- Tests live in the `tests/` directory mirroring application modules.
- Use FastAPI's TestClient for HTTP behavior.

## Type Checking
```bash
mypy src
```
Ensures Pydantic models and services maintain strict typing.

## Linting
```bash
ruff check src tests
```
Runs the configured Ruff ruleset (formatting, style, anti-patterns).

## Security Scanning
```bash
pip-audit
```
Checks Python dependencies against known vulnerabilities; CI fails on high-severity findings.

## CI Notes
GitHub Actions pipeline runs `ruff`, `mypy`, `pytest --cov`, and `pip-audit` before building/pushing the container image.
