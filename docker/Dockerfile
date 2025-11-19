FROM python:3.12-slim

# Build arg for version (needed for hatch-vcs without .git)
ARG VERSION=0.0.0+dev
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY README.md ./

# Create app directory for _version.py (hatch-vcs build hook)
RUN mkdir -p app

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY main.py ./
COPY app ./app
COPY tests ./tests
COPY pytest.ini ./

# Expose port
EXPOSE 8020

# Run application (HTTP transport for Docker, stdio is for CLI usage)
CMD ["uv", "run", "main.py", "--transport", "http"] 
