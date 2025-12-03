# Self-Hosting Forgetful on a VPS

Deploy Forgetful on a Virtual Private Server for use with Claude Code, Cursor, and other MCP-compatible AI tools.

## Hardware Requirements

Forgetful runs local ML models for embeddings and reranking by default. These are configurable (see [Configuration](./configuration.md)).

| Workload | RAM | vCPU | Disk | Notes |
|----------|-----|------|------|-------|
| **Light** (SQLite, single user) | 1-2GB | 1 | 10GB SSD | May be slow during reranking |
| **Regular** (PostgreSQL, multi-user) | 2-4GB | 2+ | 20GB+ SSD | Recommended for production |

**To reduce resource usage**: Disable cross-encoder reranking with `RERANKING_ENABLED=false`. This falls back to pure vector similarity ranking. Cloud reranking providers are on the roadmap.

---

## Quick Start

### Prerequisites
- VPS with SSH access and Docker installed
- Domain name (recommended for HTTPS)

### Deploy with SQLite (Simplest)

```bash
# Install Docker if needed
curl -fsSL https://get.docker.com | sh

# Create deployment directory
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

### Deploy with PostgreSQL (Production)

```bash
# Install Docker if needed
curl -fsSL https://get.docker.com | sh

# Create deployment directory
mkdir -p /opt/forgetful && cd /opt/forgetful

# Download files
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/docker-compose.postgres.yml -o docker-compose.yml
curl -sL https://raw.githubusercontent.com/scottrbk/forgetful/main/docker/.env.example -o .env

# IMPORTANT: Edit .env and change POSTGRES_PASSWORD
nano .env

# Start
docker compose up -d

# Verify both containers running
docker compose ps
curl http://localhost:8020/health
```

---

## Reverse Proxy (HTTPS)

**Never expose Forgetful directly to the internet.** Use a reverse proxy.

### Caddy (Recommended - Auto HTTPS)

```bash
# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install caddy
```

Create `/etc/caddy/Caddyfile`:
```caddyfile
forgetful.yourdomain.com {
    reverse_proxy localhost:8020
}
```

```bash
systemctl enable --now caddy
```

### nginx + Certbot

```bash
apt update && apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/forgetful`:
```nginx
server {
    listen 80;
    server_name forgetful.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/forgetful /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d forgetful.yourdomain.com
```

---

## Security

### Firewall

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 443/tcp  # HTTPS
ufw enable
```

### Authentication

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

### Secure .env

```bash
chmod 600 /opt/forgetful/.env
```

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

### Automated Daily Backup

Create `/etc/cron.daily/forgetful-backup`:
```bash
#!/bin/bash
BACKUP_DIR=/backups/forgetful
mkdir -p $BACKUP_DIR

# PostgreSQL:
docker exec forgetful-db pg_dump -U forgetful forgetful | gzip > $BACKUP_DIR/forgetful-$(date +%Y%m%d).sql.gz

# SQLite:
# sqlite3 /opt/forgetful/data/forgetful.db ".backup '$BACKUP_DIR/forgetful-$(date +%Y%m%d).db'"

# Keep 7 days
find $BACKUP_DIR -mtime +7 -delete
```

```bash
chmod +x /etc/cron.daily/forgetful-backup
```

---

## Troubleshooting

```bash
# Health check
curl http://localhost:8020/health

# View logs
docker compose logs -f forgetful-service

# Resource usage
docker stats

# Restart
docker compose restart

# Upgrade to latest
docker compose pull && docker compose up -d
```

**High memory/CPU?** Consider:
- `RERANKING_ENABLED=false` - Disables cross-encoder reranking (significant resource savings)
- `DENSE_SEARCH_CANDIDATES=10` - Fewer candidates to rerank (default: 20)

---

## Connect Your AI Tools

Add to your MCP client configuration:

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

See [Connectivity Guide](./connectivity_guide.md) for detailed setup per client.

---

## Further Reading

- [Configuration Reference](./configuration.md) - All environment variables
- [Connectivity Guide](./connectivity_guide.md) - Client setup
- [Offline Setup](./OFFLINE_SETUP.md) - Air-gapped deployments
