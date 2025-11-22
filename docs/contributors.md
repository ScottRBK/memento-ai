# Contributing to Forgetful

This guide covers testing and deployment workflows for contributors.

## Running with Docker with source 
This will approach will fall back to using the build and as such allow you to check any changes you have made inside of a container. 

```bash
git clone https://github.com/ScottRBK/forgetful.git
cd forgetful
```

```bash
cd docker
docker compose up -d --build
```

**Optional**: Customize configuration by copying the example environment file:

```bash
cd docker
cp .env.example .env
# Edit .env with your custom values
docker compose up -d
```


## Testing Philosophy

We focus on **integration and E2E tests** over unit tests. Tests should cover critical workflows without exhaustive edge case coverage.

### Integration Tests

**Location**: `tests/integration/`

**Purpose**: Test business logic with stubbed I/O (no real database required)

**Run locally**:
```bash
pytest tests/integration/
```

These tests use in-memory stubs and run fast (~seconds). They form the bulk of our test suite and catch 90% of issues.

### End-to-End Tests

#### SQLite E2E Tests

**Location**: `tests/e2e_sqlite/`

**Purpose**: Test complete stack with in-memory SQLite

**Requirements**: None (no Docker required)

**Run locally**:
```bash
pytest tests/e2e_sqlite/
```

**CI Status**: ✅ Runs automatically in CI workflow on every push/PR

These tests use an in-memory SQLite database for test isolation. Fast execution (~30 seconds for 94 tests) with automatic cleanup. They provide full-stack coverage without Docker dependencies, making them ideal for CI.

#### PostgreSQL E2E Tests

**Location**: `tests/e2e/`

**Purpose**: Test complete stack with real PostgreSQL

**Requirements**: PostgreSQL running in Docker

**Run locally**:
```bash
# Start PostgreSQL
docker compose up -d postgres

# Run E2E tests
pytest -m e2e
```

**CI Status**: ⚠️ Only runs on push to `main` branch or manual workflow dispatch

These tests are marked with `@pytest.mark.e2e` and validate the full application stack with PostgreSQL backend. They're heavier than SQLite E2E tests and reserved for main branch validation.

---
## Linting
linting with ruff and uv
```bash
uv tool run ruff check .
```

## CI/CD Workflows

### `ci.yml` - Continuous Integration

**Triggers**: Every push and pull request

**Purpose**: Fast feedback for contributors

**Steps**:
1. Run integration tests (stubbed, no Docker)
2. Run SQLite E2E tests (in-memory SQLite, full stack)
3. Run linting

**Status**: Blocks PR merge if fails ✅

**Test Coverage**: Integration tests validate business logic with stubs. SQLite E2E tests validate the complete application stack including real database interactions, all without Docker dependencies.

### `e2e.yml` - PostgreSQL E2E Validation

**Triggers**: Push to `main` branch OR manual workflow dispatch

**Purpose**: Validate with real PostgreSQL database

**Steps**:
1. Run PostgreSQL E2E tests (`tests/e2e/` with `-m e2e` marker)

**Status**: Reports failures but doesn't block ⚠️

**Test Coverage**: Validates full application stack with PostgreSQL backend. These are heavier tests reserved for main branch validation to ensure production database compatibility.

### `build.yml` - Docker Image Build

**Triggers**: Version tag push only (e.g., `v0.1.0`, `v1.0.0`)

**Purpose**: Build and publish release images

**Steps**:
1. Build Docker image
2. Tag with semver, SHA, and `latest`
3. Push to GitHub Container Registry (`ghcr.io/scottrbk/forgetful`)

**Note**: Only runs when you manually create a release tag

---

## Creating a Release

1. Commit your changes to `main` branch
2. Create and push a version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. Build workflow automatically creates Docker image

---

## Deployment

**Workflow**: `deploy.yml`

**Purpose**: Deploy to staging/production environments

**Method**: Self-hosted runners with sparse checkout

**Environment Selection**: Runners match environment by label (e.g., `staging` runner for staging deployment)
