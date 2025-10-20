FROM python:3.12-slim

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

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app ./app
COPY tests ./tests
COPY pytest.ini ./

# Expose port
EXPOSE 8020

# Run application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
