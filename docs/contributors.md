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

These tests are marked with `@pytest.mark.e2e` and skipped by default. They validate the full application stack.
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
2. Run linting

**Status**: Blocks PR merge if fails ✅

### `e2e.yml` - End-to-End Validation

**Triggers**: Push to `main` branch OR manual workflow dispatch

**Purpose**: Validate with real PostgreSQL

**Steps**:
1. Start PostgreSQL service in GitHub Actions
2. Run E2E tests

**Status**: Reports failures but doesn't block ⚠️

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
