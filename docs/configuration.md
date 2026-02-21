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

## Docker Deployment Options

Forgetful provides three Docker Compose configurations:

### Local Development (`docker-compose.yml`)
- **Use case**: Local development with hot reload and build context
- **Features**: Builds from source, optional volume mounting for live code updates
- **Command**: `docker compose up -d --build`

### SQLite Deployment (`docker-compose.sqlite.yml`)
- **Use case**: Production deployment with single-container simplicity
- **Features**:
  - Single container (no separate database service)
  - Persistent storage via `./data:/app/data` volume mount
  - Zero-config database setup
- **Setup**:
  ```bash
  cd docker
  cp .env.example .env
  # Edit .env: Set DATABASE=SQLite, SQLITE_PATH=data/forgetful.db
  docker compose -f docker-compose.sqlite.yml up -d
  ```
- **Important**: The `./data` directory persists your database across container restarts

### PostgreSQL Deployment (`docker-compose.postgres.yml`)
- **Use case**: Production deployment with PostgreSQL for scale and robustness
- **Features**:
  - Multi-container stack (app + PostgreSQL + pgvector)
  - Named volume for database persistence
  - Production-grade database with vector search
- **Setup**:
  ```bash
  cd docker
  cp .env.example .env
  # Edit .env: Set DATABASE=Postgres, configure POSTGRES_* settings
  docker compose -f docker-compose.postgres.yml up -d
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

## Database Configuration (SQLite/PostgreSQL)

### `DATABASE`
- **Default**: `SQLite`
- **Description**: Database backend to use
- **Values**:
  - `SQLite` - Lightweight, zero-config (default, recommended for getting started)
  - `Postgres` - Production-grade, scalable (recommended for high load)
- **Example**: `DATABASE=SQLite`

### SQLite Settings

#### `SQLITE_PATH`
- **Default**: `forgetful.db`
- **Description**: File path for SQLite database
- **Notes**:
  - Relative paths are relative to the project root (or `/app` in Docker containers)
  - **Docker deployment**: Use `data/forgetful.db` with volume mount `./data:/app/data` to persist data across container restarts (see `docker-compose.sqlite.yml`)
  - Without volume mounting, the database will be ephemeral and lost on container removal
- **Example**: `SQLITE_PATH=data/forgetful.db`

#### `SQLITE_MEMORY`
- **Default**: `false`
- **Description**: Use in-memory database (ephemeral, for testing only)
- **Values**: `true`, `false`
- **Example**: `SQLITE_MEMORY=false`

### PostgreSQL Settings

**Note**: These settings only apply when `DATABASE=Postgres`

#### `POSTGRES_HOST`
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
- **� Security**: Change this in production deployments
- **Example**: `POSTGRES_USER=my_secure_user`

### `POSTGRES_PASSWORD`
- **Default**: `forgetful`
- **Description**: PostgreSQL password for authentication
- **� Security**: **Always change this in production deployments**
- **Example**: `POSTGRES_PASSWORD=my_secure_password_123`

### Common Database Settings

#### `DB_LOGGING`
- **Default**: `false`
- **Description**: Enable SQL query logging for debugging (applies to both SQLite and PostgreSQL)
- **Values**: `true`, `false`
- **Note**: Very verbose - use only for troubleshooting
- **Example**: `DB_LOGGING=true`

---

## Authentication Configuration

Forgetful leverages **FastMCP's built-in authentication system** via environment variables. This provides flexible auth options without custom code.

**📚 Official Documentation**:
- [FastMCP Auth Guide](https://fastmcp.wiki/en/servers/auth/authentication)
- [Auth Examples](https://github.com/jlowin/fastmcp/tree/main/docs/servers/auth)

---

### Authentication Modes

#### **No Authentication (Default)**

When `FASTMCP_SERVER_AUTH` is **not set**, authentication is disabled and all requests use the default user:

```bash
# .env - No auth configured
DEFAULT_USER_ID="default-user-id"
DEFAULT_USER_NAME="default-user-name"
DEFAULT_USER_EMAIL="default.user@forgetful.dev"
```

#### **Token Introspection (OAuth 2.0 RFC 7662)**

Validates opaque bearer tokens via an introspection endpoint. Recommended for microservices architectures.

```bash
# .env - Token Introspection
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier
FASTMCP_SERVER_AUTH_INTROSPECTION_URL=https://auth.yourcompany.com/oauth/introspect
FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID=forgetful-resource-server
FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET=your-client-secret
FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES=api:read,api:write
```

**How it works**:
- Client sends bearer token in `Authorization` header
- Forgetful validates token via introspection endpoint
- User provisioned from token claims (`sub`, `name`, `email`)

#### **JWT Verification**

Validates JWT tokens using JWKS endpoint or public key. Ideal for stateless authentication.

```bash
# .env - JWT Verification
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.jwt.JWTVerifier
FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://auth.yourcompany.com/.well-known/jwks.json
FASTMCP_SERVER_AUTH_JWT_ISSUER=https://auth.yourcompany.com
FASTMCP_SERVER_AUTH_JWT_AUDIENCE=forgetful-api
FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=api:read,api:write
```

**How it works**:
- Client sends JWT in `Authorization: Bearer <token>` header
- Forgetful validates signature, issuer, audience, expiration
- User provisioned from JWT claims (`sub`, `name`, `email`)

#### **OAuth Proxy (GitHub, Google, etc.)**

For OAuth providers that don't support Dynamic Client Registration (DCR). Pre-register your app with the provider.

```bash
# .env - GitHub OAuth Proxy
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.github.GitHubProvider
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID=Ov23li...
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET=abc123...
FASTMCP_SERVER_AUTH_GITHUB_BASE_URL=https://forgetful.yourcompany.com
```

**Supported Providers**:
- `fastmcp.server.auth.providers.github.GitHubProvider`
- `fastmcp.server.auth.providers.google.GoogleProvider`
- See [FastMCP docs](https://github.com/jlowin/fastmcp/tree/main/docs/servers/auth) for full list

---

### Configuration Reference

#### `FASTMCP_SERVER_AUTH`
- **Default**: Not set (authentication disabled)
- **Description**: Fully-qualified class path to FastMCP auth provider
- **Values**:
  - *Omit* - No authentication (default user mode)
  - `fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier` - Token introspection
  - `fastmcp.server.auth.providers.jwt.JWTVerifier` - JWT verification
  - `fastmcp.server.auth.providers.github.GitHubProvider` - GitHub OAuth
  - `fastmcp.server.auth.providers.google.GoogleProvider` - Google OAuth
- **Example**: `FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.jwt.JWTVerifier`

#### Default User Settings (when auth is disabled)

##### `DEFAULT_USER_ID`
- **Default**: `default-user-id`
- **Description**: External user ID when authentication is disabled
- **Example**: `DEFAULT_USER_ID=local-dev-user`

##### `DEFAULT_USER_NAME`
- **Default**: `default-user-name`
- **Description**: Display name for default user
- **Example**: `DEFAULT_USER_NAME=Local Developer`

##### `DEFAULT_USER_EMAIL`
- **Default**: `default-user-email`
- **Description**: Email address for default user
- **Example**: `DEFAULT_USER_EMAIL=dev@localhost`

#### OAuth Storage Configuration

##### `OAUTH_STORAGE_PATH`
- **Default**: Platform-specific user data directory (e.g., `~/.local/share/forgetful/oauth`)
- **Description**: Directory where OAuth tokens and state are persisted
- **Purpose**: Stores authentication tokens between restarts when using OAuth providers (GitHub, Google, etc.)
- **Note**: This directory contains sensitive authentication data - ensure proper file permissions
- **Example**: `OAUTH_STORAGE_PATH=/app/data/oauth`

---

### User Provisioning

When authentication is enabled, Forgetful automatically provisions users from token claims:

**Required Claims**:
- `sub` - Subject identifier (maps to `external_id`)
- `name` OR `preferred_username` - Display name

**Optional Claims**:
- `email` - Email address (defaults to empty string)

**Auto-provisioning behavior**:
- First request: User created in database
- Subsequent requests: User retrieved by `external_id`
- Updates: Name/email updated if changed in token

**Example token claims**:
```json
{
  "sub": "auth0|507f1f77bcf86cd799439011",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "iat": 1700000000,
  "exp": 1700003600
}
```

---

### Security Best Practices

1. **Production Deployments**:
   - Always enable authentication (`FASTMCP_SERVER_AUTH`)
   - Use HTTPS for all endpoints
   - Rotate client secrets regularly
   - Bind to localhost: `BIND_ADDRESS=127.0.0.1`

2. **Token Scopes**:
   - Define required scopes: `FASTMCP_SERVER_AUTH_*_REQUIRED_SCOPES`
   - Implement least-privilege access

3. **Development vs Production**:
   ```bash
   # Development - No auth for local testing
   # FASTMCP_SERVER_AUTH not set
   DEFAULT_USER_ID=dev-user

   # Production - JWT auth required
   FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.jwt.JWTVerifier
   FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://auth.company.com/.well-known/jwks.json
   FASTMCP_SERVER_AUTH_JWT_ISSUER=https://auth.company.com
   FASTMCP_SERVER_AUTH_JWT_AUDIENCE=forgetful-prod
   ```

---

### Troubleshooting

**"Authentication required but no bearer token provided"**:
- Client must send `Authorization: Bearer <token>` header
- Check MCP client configuration

**"Token contains no 'sub' claim"**:
- Token is invalid or missing required claim
- Verify token with JWT debugger (jwt.io)

**"Token requires 'name' or 'preferred_username' claim"**:
- Token missing user display name
- Configure IdP to include `name` claim

**401 Unauthorized**:
- Token expired, invalid signature, or wrong audience
- Enable debug logging: `LOG_LEVEL=DEBUG`

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

## Project Configuration

### `PROJECT_DESCRIPTION_MAX_LENGTH`
- **Default**: `5000`
- **Description**: Maximum characters for project descriptions
- **Purpose**: Text field with reasonable cap for detailed project documentation
- **Example**: `PROJECT_DESCRIPTION_MAX_LENGTH=5000`

### `PROJECT_NOTES_MAX_LENGTH`
- **Default**: `4000`
- **Description**: Maximum characters for project notes
- **Purpose**: Text field with reasonable cap for project-level annotations
- **Example**: `PROJECT_NOTES_MAX_LENGTH=4000`

---

## Code Artifact Configuration

### `CODE_ARTIFACT_TITLE_MAX_LENGTH`
- **Default**: `500`
- **Description**: Maximum characters for code artifact titles
- **Note**: Database limit is String(500)
- **Example**: `CODE_ARTIFACT_TITLE_MAX_LENGTH=500`

### `CODE_ARTIFACT_DESCRIPTION_MAX_LENGTH`
- **Default**: `5000`
- **Description**: Maximum characters for code artifact descriptions
- **Purpose**: Reasonable cap for text field describing the code snippet
- **Example**: `CODE_ARTIFACT_DESCRIPTION_MAX_LENGTH=5000`

### `CODE_ARTIFACT_CODE_MAX_LENGTH`
- **Default**: `50000`
- **Description**: Maximum characters for code artifact content (~50KB)
- **Purpose**: Allows storage of large code snippets
- **Example**: `CODE_ARTIFACT_CODE_MAX_LENGTH=50000`

### `CODE_ARTIFACT_TAGS_MAX_COUNT`
- **Default**: `10`
- **Description**: Maximum number of tags per code artifact
- **Purpose**: Categorization and filtering
- **Example**: `CODE_ARTIFACT_TAGS_MAX_COUNT=10`

---

## Document Configuration

### `DOCUMENT_TITLE_MAX_LENGTH`
- **Default**: `500`
- **Description**: Maximum characters for document titles
- **Note**: Database limit is String(500)
- **Example**: `DOCUMENT_TITLE_MAX_LENGTH=500`

### `DOCUMENT_DESCRIPTION_MAX_LENGTH`
- **Default**: `5000`
- **Description**: Maximum characters for document descriptions
- **Purpose**: Reasonable cap for text field describing the document
- **Example**: `DOCUMENT_DESCRIPTION_MAX_LENGTH=5000`

### `DOCUMENT_CONTENT_MAX_LENGTH`
- **Default**: `100000`
- **Description**: Maximum characters for document content (~100KB)
- **Purpose**: Allows storage of large documents
- **Example**: `DOCUMENT_CONTENT_MAX_LENGTH=100000`

### `DOCUMENT_TAGS_MAX_COUNT`
- **Default**: `10`
- **Description**: Maximum number of tags per document
- **Purpose**: Categorization and filtering
- **Example**: `DOCUMENT_TAGS_MAX_COUNT=10`

---

## Entity Configuration

### `ENTITY_NAME_MAX_LENGTH`
- **Default**: `200`
- **Description**: Maximum characters for entity names
- **Note**: Database limit is String(200)
- **Example**: `ENTITY_NAME_MAX_LENGTH=200`

### `ENTITY_TYPE_MAX_LENGTH`
- **Default**: `100`
- **Description**: Maximum characters for custom entity types
- **Examples**: "organization", "person", "device", "team"
- **Example**: `ENTITY_TYPE_MAX_LENGTH=100`

### `ENTITY_NOTES_MAX_LENGTH`
- **Default**: `4000`
- **Description**: Maximum characters for entity notes
- **Purpose**: Reasonable cap for text field with entity annotations
- **Example**: `ENTITY_NOTES_MAX_LENGTH=4000`

### `ENTITY_TAGS_MAX_COUNT`
- **Default**: `10`
- **Description**: Maximum number of tags per entity
- **Purpose**: Categorization and filtering
- **Example**: `ENTITY_TAGS_MAX_COUNT=10`

### `ENTITY_RELATIONSHIP_TYPE_MAX_LENGTH`
- **Default**: `100`
- **Description**: Maximum characters for relationship type labels
- **Examples**: "works_at", "owns", "manages", "depends_on"
- **Example**: `ENTITY_RELATIONSHIP_TYPE_MAX_LENGTH=100`

---

## Activity Tracking Configuration

Activity tracking provides an audit log of all entity lifecycle events (created, updated, deleted). This is an **experimental feature**.

> **⚠️ Experimental Feature**
>
> Activity tracking uses an async event-driven architecture that may cause issues with SQLite backends due to connection pooling conflicts.
>
> **Recommendations:**
> - **PostgreSQL**: Safe to enable, but still considered experimental
> - **SQLite**: Leave disabled unless you have a specific need and are prepared to troubleshoot potential issues
> - **Production**: Test thoroughly before enabling in production environments

### `ACTIVITY_ENABLED`
- **Default**: `false`
- **Description**: Enable activity event tracking
- **Values**: `true`, `false`
- **Note**: When disabled, no events are recorded and the activity API returns empty results
- **Example**: `ACTIVITY_ENABLED=true`

### `ACTIVITY_RETENTION_DAYS`
- **Default**: `null` (forever)
- **Description**: Number of days to keep activity events before automatic cleanup
- **Values**:
  - `null` or omit - Keep events forever
  - `30` - Keep events for 30 days
  - `90` - Keep events for 90 days
- **Behavior**: Cleanup happens lazily on API access (not via scheduled job)
- **Example**: `ACTIVITY_RETENTION_DAYS=90`

### `ACTIVITY_TRACK_READS`
- **Default**: `false`
- **Description**: Track read and query operations (in addition to create/update/delete)
- **Values**: `true`, `false`
- **⚠️ Warning**: Enabling this can generate high event volume in active systems
- **Example**: `ACTIVITY_TRACK_READS=false`

### SSE Streaming Configuration

#### `SSE_MAX_QUEUE_SIZE`
- **Default**: `1000`
- **Description**: Maximum events per SSE subscriber queue (backpressure handling)
- **Purpose**: When the queue is full, new events are dropped to prevent memory exhaustion
- **Behavior**: Clients can detect dropped events via sequence number gaps and resync via REST API
- **Note**: Increase for high-throughput scenarios where bulk operations are common
- **Example**: `SSE_MAX_QUEUE_SIZE=2000`

### Example Configuration

```bash
# Enable activity tracking with 90-day retention
ACTIVITY_ENABLED=true
ACTIVITY_RETENTION_DAYS=90
ACTIVITY_TRACK_READS=false
```

---

## Search Configuration

### `EMBEDDING_PROVIDER`
- **Default**: `FastEmbed`
- **Description**: Embedding generation provider
- **Current Support**: FastEmbed | Azure | Google | OpenAI | Ollama
- **Example**: `EMBEDDING_PROVIDER=FastEmbed`

### `EMBEDDING_MODEL`
- **Default**: `BAAI/bge-small-en-v1.5`
- **Description**: Embedding model identifier
- **Properties**: 384 dimensions, optimized for semantic similarity
- **Note**: Changing this requires re-embedding all existing memories. See [Embedding Migration Guide](./embedding_migration.md)
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

### Azure Embedding Provider Configuration

**Note**: These settings only apply when `EMBEDDING_PROVIDER=Azure`

#### `AZURE_ENDPOINT`
- **Default**: (empty string)
- **Description**: Azure OpenAI service endpoint URL
- **Format**: `https://<resource-name>.openai.azure.com/`
- **Example**: `AZURE_ENDPOINT=https://my-openai.openai.azure.com/`

#### `AZURE_DEPLOYMENT`
- **Default**: (empty string)
- **Description**: Azure OpenAI embedding model deployment name
- **Example**: `AZURE_DEPLOYMENT=text-embedding-ada-002`

#### `AZURE_API_VERSION`
- **Default**: (empty string)
- **Description**: Azure OpenAI API version to use
- **Example**: `AZURE_API_VERSION=2023-05-15`

#### `AZURE_API_KEY`
- **Default**: (empty string)
- **Description**: Azure OpenAI API authentication key
- **Security**: **Keep this secret** - never commit to version control
- **Example**: `AZURE_API_KEY=your-azure-api-key-here`

### Google Embedding Provider Configuration

**Note**: These settings only apply when `EMBEDDING_PROVIDER=Google`

#### `GOOGLE_AI_API_KEY`
- **Default**: (empty string)
- **Description**: Google AI API key for embedding generation
- **Security**: **Keep this secret** - never commit to version control
- **Example**: `GOOGLE_AI_API_KEY=your-google-api-key-here`

### OpenAI Embedding Provider Configuration

**Note**: These settings only apply when `EMBEDDING_PROVIDER=OpenAI`

> **Dimension mismatch warning**: If switching from another provider (e.g., FastEmbed at 384 dimensions) to OpenAI, existing memory embeddings will be incompatible. You must re-embed all existing memories after changing providers. See the [Embedding Migration Guide](./embedding_migration.md) for instructions.

#### `OPENAI_API_KEY`
- **Default**: (empty string)
- **Description**: OpenAI API key for embedding generation
- **Security**: **Keep this secret** - never commit to version control
- **Example**: `OPENAI_API_KEY=sk-your-openai-api-key-here`

#### `OPENAI_BASE_URL`
- **Default**: (empty string)
- **Description**: Custom base URL for OpenAI-compatible endpoints (llama.cpp, vLLM, LiteLLM)
- **Note**: When set, `OPENAI_API_KEY` becomes optional (a placeholder is used automatically)
- **Example**: `OPENAI_BASE_URL=http://localhost:8080/v1`

#### `OPENAI_SUPPORTS_DIMENSIONS`
- **Default**: `true`
- **Description**: Whether the endpoint supports the `dimensions` parameter
- **Note**: Set to `false` for endpoints that error on the dimensions param (e.g. llama.cpp)
- **Example**: `OPENAI_SUPPORTS_DIMENSIONS=false`

### Ollama Embedding Provider Configuration

**Note**: These settings only apply when `EMBEDDING_PROVIDER=Ollama`

> Ollama uses native async via the `ollama` Python SDK. No API key required (Ollama runs locally). Install with `pip install forgetful-ai[ollama]`.

#### `OLLAMA_BASE_URL`
- **Default**: `http://localhost:11434`
- **Description**: Ollama server URL
- **Example**: `OLLAMA_BASE_URL=http://localhost:11434`

### Re-ranking Configuration

#### `RERANKING_ENABLED`
- **Default**: `true`
- **Description**: Enable re-ranking of search results for improved relevance
- **Values**: `true`, `false`
- **Note**: Improves search quality at the cost of additional processing
- **Example**: `RERANKING_ENABLED=true`

#### `RERANKING_PROVIDER`
- **Default**: `FastEmbed`
- **Description**: Re-ranking model provider
- **Current Support**: FastEmbed
- **Example**: `RERANKING_PROVIDER=FastEmbed`

#### `RERANKING_MODEL`
- **Default**: `Xenova/ms-marco-MiniLM-L-12-v2`
- **Description**: Re-ranking model identifier
- **Purpose**: Optimized for search result re-ranking
- **Example**: `RERANKING_MODEL=Xenova/ms-marco-MiniLM-L-12-v2`

### FastEmbed Cache Configuration

#### `FASTEMBED_CACHE_DIR`
- **Default**: Platform-specific user data directory (e.g., `~/.local/share/forgetful/models/fastembed`)
- **Description**: Directory where FastEmbed models are cached
- **Purpose**: Avoids re-downloading models on each startup
- **Note**: Can be customized for offline deployments (see [Offline Setup Guide](OFFLINE_SETUP.md))
- **Example**: `FASTEMBED_CACHE_DIR=/app/data/models/fastembed`

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
� **Warning**: Very verbose output, use only for troubleshooting

---

## Additional Resources

- [README.md](../README.md) - Getting started guide
- [Connectivity Guide](connectivity_guide.md) - Connecting MCP clients
- [Search Documentation](search.md) - Search architecture details
- [Settings Source](../app/config/settings.py) - Default values and validation
