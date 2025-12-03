# Self-Hosting Forgetful on a VPS

Deploy Forgetful on a Virtual Private Server for use with Claude Code, Cursor, and other MCP-compatible AI tools.

## Prerequisites

Before deploying Forgetful, ensure your VPS has:

- **Docker & Docker Compose** installed
- **Reverse proxy** (nginx, Caddy, Traefik) for HTTPS termination
- **Firewall** configured to only expose necessary ports (SSH, HTTPS)

Resources for VPS setup:
- [Docker Installation Guide](https://docs.docker.com/engine/install/)
- [Caddy Reverse Proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy)
- [nginx Reverse Proxy](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)

## Hardware Requirements

Forgetful runs local ML models for embeddings and reranking by default. These are configurable (see [Configuration](./configuration.md)).

| Workload | RAM | vCPU | Disk |
|----------|-----|------|------|
| **Light** (SQLite, single user) | 1-2GB | 1 | 10GB SSD |
| **Regular** (PostgreSQL, multi-user) | 2-4GB | 2+ | 20GB+ SSD |

**To reduce resource usage**: Set `RERANKING_ENABLED=false` to disable cross-encoder reranking. This falls back to pure vector similarity ranking. Cloud reranking providers are on the roadmap.

---

## Deployment

### SQLite (Simpler)

```bash
mkdir -p /opt/forgetful/data && cd /opt/forgetful

# Download files
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/docker-compose.sqlite.yml -o docker-compose.yml
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/.env.example -o .env

# Configure for SQLite
sed -i 's/DATABASE=Postgres/DATABASE=SQLite/' .env

# Start
docker compose up -d

# Verify
curl http://localhost:8020/health
```

### PostgreSQL (Production)

```bash
mkdir -p /opt/forgetful && cd /opt/forgetful

# Download files
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/docker-compose.postgres.yml -o docker-compose.yml
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/.env.example -o .env

# IMPORTANT: Edit .env and change POSTGRES_PASSWORD
nano .env

# Start
docker compose up -d

# Verify
docker compose ps
curl http://localhost:8020/health
```

---

## Configuration

Key settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE` | `Postgres` | `Postgres` or `SQLite` |
| `POSTGRES_PASSWORD` | `forgetful` | **Change this!** |
| `BIND_ADDRESS` | `127.0.0.1` | Keep as localhost; expose via reverse proxy |
| `SERVER_PORT` | `8020` | Internal port for MCP endpoint |
| `RERANKING_ENABLED` | `true` | Set `false` to reduce resource usage |
| `DENSE_SEARCH_CANDIDATES` | `20` | Lower = faster reranking |

Secure your `.env` file: `chmod 600 /opt/forgetful/.env`

For all options, see [Configuration Reference](./configuration.md).

---

## Authentication

**Don't run without authentication in production.** Enable via `.env`:

```env
# JWT (recommended)
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.jwt.JWTVerifier
FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://your-auth-server.com/.well-known/jwks.json
FASTMCP_SERVER_AUTH_JWT_ISSUER=https://your-auth-server.com
FASTMCP_SERVER_AUTH_JWT_AUDIENCE=forgetful-api

# Or GitHub OAuth
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.github.GitHubProvider
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID=your-client-id
FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET=your-client-secret
FASTMCP_SERVER_AUTH_GITHUB_BASE_URL=https://forgetful.yourdomain.com
```

See [FastMCP Auth Docs](https://fastmcp.wiki/en/servers/auth/authentication) for details.

---

## Backups

### SQLite
```bash
sqlite3 /opt/forgetful/data/forgetful.db ".backup '/backups/forgetful-$(date +%Y%m%d).db'"
```

### PostgreSQL
```bash
docker exec forgetful-db pg_dump -U forgetful forgetful | gzip > /backups/forgetful-$(date +%Y%m%d).sql.gz
```

---

## Operations

```bash
# Health check
curl http://localhost:8020/health

# View logs
docker compose logs -f forgetful-service

# Resource usage
docker stats

# Restart
docker compose restart

# Upgrade
docker compose pull && docker compose up -d
```

---

## Connect Your AI Tools

Point your reverse proxy to `localhost:8020`, then configure your MCP client:

```json
{
  "mcpServers": {
    "forgetful": {
      "type": "http",
      "url": "https://forgetful.yourdomain.com/mcp"
    }
  }
}
```

See [Connectivity Guide](./connectivity_guide.md) for client-specific setup.

---

## Further Reading

- [Configuration Reference](./configuration.md) – All environment variables
- [Connectivity Guide](./connectivity_guide.md) – Client setup
- [Offline Setup](./OFFLINE_SETUP.md) – Air-gapped deployments
