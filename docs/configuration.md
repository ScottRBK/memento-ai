# Configuration Guide

This guide explains all available environment variables for configuring Forgetful.

## Quick Start

All configuration is optional. If no `.env` file exists, Forgetful uses sensible defaults from `app/config/settings.py`.

To customize configuration:
```bash
cd docker
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

---

## Application Info

### `SERVICE_NAME`
- **Default**: `Forgetful`
- **Description**: Display name for the service in logs and metrics
- **Example**: `SERVICE_NAME=MyMemoryService`

### `SERVICE_VERSION`
- **Default**: `v0.0.1`
- **Description**: Version identifier for the service
- **Example**: `SERVICE_VERSION=v1.2.3`

### `SERVICE_DESCRIPTION`
- **Default**: `Forgetful Memory Service`
- **Description**: Human-readable description of the service
- **Example**: `SERVICE_DESCRIPTION="My custom memory MCP server"`

---

## Server Configuration

### `SERVER_HOST`
- **Default**: `0.0.0.0`
- **Description**: Network interface the server binds to
- **Values**:
  - `0.0.0.0` - Listen on all interfaces (default for container)
  - `127.0.0.1` - Listen only on localhost
- **Example**: `SERVER_HOST=0.0.0.0`

### `SERVER_PORT`
- **Default**: `8020`
- **Description**: Port number the MCP server listens on
- **Note**: If changed, update your MCP client configuration and Docker port mapping
- **Example**: `SERVER_PORT=8020`

### `LOG_LEVEL`
- **Default**: `INFO`
- **Description**: Logging verbosity level
- **Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Example**: `LOG_LEVEL=DEBUG` (for troubleshooting)

### `LOG_FORMAT`
- **Default**: `console`
- **Description**: Log output format
- **Values**:
  - `console` - Human-readable format (recommended for development)
  - `json` - Structured JSON format (recommended for production)
- **Example**: `LOG_FORMAT=json`

---

## Docker Configuration

### `COMPOSE_PROJECT_NAME`
- **Default**: `forgetful`
- **Description**: Docker Compose project name (prefixes container and volume names)
- **Example**: `COMPOSE_PROJECT_NAME=my-forgetful-stack`

### `BIND_ADDRESS`
- **Default**: `127.0.0.1`
- **Description**: Host address Docker exposes the service on
- **Values**:
  - `127.0.0.1` - Localhost only (secure, recommended)
  - `0.0.0.0` - All interfaces (development only, insecure on public networks)
- **Example**: `BIND_ADDRESS=127.0.0.1`

---

## Database Configuration

### `DATABASE`
- **Default**: `Postgres`
- **Description**: Database type identifier
- **Note**: Currently only PostgreSQL is supported
- **Example**: `DATABASE=Postgres`

### `POSTGRES_HOST`
- **Default**: `127.0.0.1`
- **Description**: PostgreSQL server hostname
- **Values**:
  - `forgetful-db` - When running in Docker (container name)
  - `127.0.0.1` - When running locally outside Docker
- **Example**: `POSTGRES_HOST=forgetful-db`

### `PGPORT`
- **Default**: `5099`
- **Description**: PostgreSQL server port
- **Note**: Uses non-standard port to avoid conflicts with existing PostgreSQL installations
- **Example**: `PGPORT=5099`

### `POSTGRES_DB`
- **Default**: `forgetful`
- **Description**: Database name to connect to
- **Example**: `POSTGRES_DB=forgetful`

### `POSTGRES_USER`
- **Default**: `forgetful`
- **Description**: PostgreSQL username for authentication
- **  Security**: Change this in production deployments
- **Example**: `POSTGRES_USER=my_secure_user`

### `POSTGRES_PASSWORD`
- **Default**: `forgetful`
- **Description**: PostgreSQL password for authentication
- **  Security**: **Always change this in production deployments**
- **Example**: `POSTGRES_PASSWORD=my_secure_password_123`

### `DB_LOGGING`
- **Default**: `false`
- **Description**: Enable SQL query logging for debugging
- **Values**: `true`, `false`
- **Note**: Very verbose - use only for troubleshooting
- **Example**: `DB_LOGGING=true`

---

## Authentication Configuration

  **Note**: Authentication is not yet implemented (roadmap feature)

### `AUTH_ENABLED`
- **Default**: `false`
- **Description**: Enable authentication middleware
- **Current Status**: Always `false` (auth not implemented)
- **Example**: `AUTH_ENABLED=false`

### `DEFAULT_USER_ID`
- **Default**: `default-user-id`
- **Description**: User ID to use when auth is disabled
- **Example**: `DEFAULT_USER_ID=test-user-123`

### `DEFAULT_USER_NAME`
- **Default**: `default-user-name`
- **Description**: Display name for default user
- **Example**: `DEFAULT_USER_NAME=Test User`

### `DEFAULT_USER_EMAIL`
- **Default**: `default-user-email`
- **Description**: Email address for default user
- **Example**: `DEFAULT_USER_EMAIL=test@example.com`

---

## Memory Configuration

These settings control the atomic memory system's behavior and constraints.

### `MEMORY_TITLE_MAX_LENGTH`
- **Default**: `200`
- **Description**: Maximum characters for memory titles
- **Rationale**: Titles must be "easily titled" and scannable at a glance
- **Atomic Memory Principle**: Force concise, clear titles
- **Example**: `MEMORY_TITLE_MAX_LENGTH=200`

### `MEMORY_CONTENT_MAX_LENGTH`
- **Default**: `2000`
- **Description**: Maximum characters for memory content (~300-400 words)
- **Rationale**: Enforces single-concept atomic memories (Zettelkasten principle)
- **Note**: For longer content, use Documents and link to them
- **Example**: `MEMORY_CONTENT_MAX_LENGTH=2000`

### `MEMORY_CONTEXT_MAX_LENGTH`
- **Default**: `500`
- **Description**: Maximum characters for memory context field
- **Purpose**: Brief explanation of WHY this memory matters, HOW it relates, WHAT implications
- **Example**: `MEMORY_CONTEXT_MAX_LENGTH=500`

### `MEMORY_KEYWORDS_MAX_COUNT`
- **Default**: `10`
- **Description**: Maximum number of keywords per memory
- **Purpose**: Semantic clustering and search optimization
- **Example**: `MEMORY_KEYWORDS_MAX_COUNT=10`

### `MEMORY_TAGS_MAX_COUNT`
- **Default**: `10`
- **Description**: Maximum number of tags per memory
- **Purpose**: Categorization and filtering
- **Example**: `MEMORY_TAGS_MAX_COUNT=10`

### `MEMORY_TOKEN_BUDGET`
- **Default**: `8000`
- **Description**: Maximum tokens for query results (protects LLM context window)
- **Behavior**: System prioritizes by importance, then truncates to fit budget
- **Note**: Increase if you have larger context windows; decrease for smaller models
- **Example**: `MEMORY_TOKEN_BUDGET=8000`

### `MEMORY_MAX_MEMORIES`
- **Default**: `20`
- **Description**: Maximum number of memories returned per query
- **Behavior**: Hard limit regardless of token budget
- **Example**: `MEMORY_MAX_MEMORIES=20`

### `MEMORY_NUM_AUTO_LINK`
- **Default**: `3`
- **Description**: Number of similar memories to automatically link on creation
- **Values**:
  - `0` - Disable auto-linking
  - `1-10` - Number of links to create
- **Rationale**: Builds knowledge graph automatically
- **Example**: `MEMORY_NUM_AUTO_LINK=5`

---

## Search Configuration

### `EMBEDDING_PROVIDER`
- **Default**: `FastEmbed`
- **Description**: Embedding generation provider
- **Current Support**: Only `FastEmbed` is currently implemented
- **Example**: `EMBEDDING_PROVIDER=FastEmbed`

### `EMBEDDING_MODEL`
- **Default**: `BAAI/bge-small-en-v1.5`
- **Description**: Embedding model identifier
- **Properties**: 384 dimensions, optimized for semantic similarity
- **Note**: Changing this requires re-embedding all existing memories
- **Example**: `EMBEDDING_MODEL=BAAI/bge-small-en-v1.5`

### `EMBEDDING_DIMENSIONS`
- **Default**: `384`
- **Description**: Vector dimensions for embeddings
- **Note**: Must match the model's output dimensions
- **Example**: `EMBEDDING_DIMENSIONS=384`

### `DENSE_SEARCH_CANDIDATES`
- **Default**: `50`
- **Description**: Number of candidates to retrieve from dense (embedding) search before re-ranking
- **Performance**: Higher values = better recall, slower queries
- **Example**: `DENSE_SEARCH_CANDIDATES=100`

---

## Configuration Hierarchy

Settings are resolved in this order (highest priority first):

1. **Environment variables** (from `.env` file or system environment)
2. **Defaults** (from `app/config/settings.py`)

---

## Common Configuration Scenarios

### Local Development
```bash
# docker/.env
SERVER_PORT=8020
POSTGRES_HOST=127.0.0.1
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

### Docker Development
```bash
# docker/.env
SERVER_PORT=8020
POSTGRES_HOST=forgetful-db
LOG_LEVEL=INFO
LOG_FORMAT=console
```

### Production
```bash
# docker/.env
SERVER_PORT=8020
POSTGRES_HOST=forgetful-db
POSTGRES_USER=secure_user
POSTGRES_PASSWORD=<strong-password>
LOG_LEVEL=WARNING
LOG_FORMAT=json
BIND_ADDRESS=127.0.0.1
```

### High-Volume / Large Context
```bash
# docker/.env
MEMORY_TOKEN_BUDGET=16000
MEMORY_MAX_MEMORIES=50
DENSE_SEARCH_CANDIDATES=100
```

---

## Security Best Practices

1. **Always change database credentials in production**
   ```bash
   POSTGRES_USER=my_secure_user
   POSTGRES_PASSWORD=<use-a-strong-password>
   ```

2. **Use localhost binding for security**
   ```bash
   BIND_ADDRESS=127.0.0.1
   ```

3. **Use structured logging in production**
   ```bash
   LOG_FORMAT=json
   LOG_LEVEL=WARNING
   ```

4. **Keep `.env` out of version control**
   - Already configured in `.gitignore`
   - Use `.env.example` as template

---

## Troubleshooting

### Database Connection Issues
- Verify `POSTGRES_HOST` matches your deployment:
  - `forgetful-db` for Docker
  - `127.0.0.1` for local
- Check port with: `docker compose ps` or `netstat -an | grep 5099`

### Port Conflicts
- Change `SERVER_PORT` and `PGPORT` if defaults conflict
- Update Docker port mappings in `docker-compose.yml`
- Update MCP client configuration

### Search Performance
- Increase `DENSE_SEARCH_CANDIDATES` for better results
- Decrease for faster queries
- Adjust `MEMORY_TOKEN_BUDGET` based on your LLM's context window

### Debug Mode
```bash
LOG_LEVEL=DEBUG
DB_LOGGING=true
```
  **Warning**: Very verbose output, use only for troubleshooting

---

## Additional Resources

- [README.md](../README.md) - Getting started guide
- [Connectivity Guide](connectivity_guide.md) - Connecting MCP clients
- [Search Documentation](search.md) - Search architecture details
- [Settings Source](../app/config/settings.py) - Default values and validation
