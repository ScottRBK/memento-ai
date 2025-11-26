# Forgetful Development Guide

## Architecture
Layered architecture:
 routes -> services -> protocols -> repositories/adapters 
No pollution of service layer with integration/implementation details

## Testing Philosophy
We focus on **integration and E2E tests** over unit tests. Tests should cover critical workflows without exhaustive edge case coverage.

### Integration Tests
**Location**: `tests/integration/`
**Purpose**: Test business logic with stubbed I/O (no real database required)
**Run locally**:
```bash
uv run pytest tests/integration/
```
These tests use in-memory stubs and run fast (~seconds). They form the bulk of our test suite and catch 90% of issues.

### End-to-End Tests

#### SQLite E2E Tests
**Location**: `tests/e2e_sqlite/`
**Purpose**: Test complete stack with in-memory SQLite
**Requirements**: None (no Docker required)
**Run locally**:
```bash
uv run pytest tests/e2e_sqlite/
```
These tests use an in-memory SQLite database for test isolation. Fast execution with automatic cleanup. 

#### PostgreSQL E2E Tests
**Location**: `tests/e2e/`
**Purpose**: Test complete stack with real PostgreSQL
**Requirements**: PostgreSQL running in Docker
**Run locally**:
```bash
docker compose up -d postgres
uv run pytest -m e2e
```