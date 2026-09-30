# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- `Integration Tests` CI job no longer fails due to flaky HashiCorp apt key install. Vault CLI
  dependency removed; `Configure Vault` step now configures the Vault service container via its
  HTTP API using `curl`. Vault service image pinned from `latest` to `1.15.6`.

## [1.0.1] - 2026-04-11

### Fixed
- `ConnectionManager.getStats()` no longer throws `NullPointerException` when called before any
  AMQP channel has been opened. `CachingConnectionFactory.getCacheProperties()` is now wrapped in
  a try-catch so `/actuator/health` probes succeed during pod startup.
