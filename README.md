# Forgetful

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![MCP](https://img.shields.io/badge/MCP-server-purple)

**A unified memory layer for AI agents across platforms**

![Banner](/docs/images/hero_banner.png)

---

## Table of Contents

- [About](#about)
- [What is Forgetful?](#what-is-forgetful)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Some Examples](#usage-example)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## About

Using multiple AI platforms and tools means constantly repeating context. Each tool has its own memory management, creating silos where knowledge and **experience** is trapped within individual applications.

## How Forgetful Helps

![Layers](docs/images/layers.png)
Forgetful provides cross platform **memory** for AI agents:
- Stop repeating yourself across Claude, ChatGPT, and other AI platforms.
- Share context seamlessly through protocol-level integration (MCP)
- Build knowledge graphs that connect related memories automatically
- Recall context the way humans do—through atomic concepts and associations
- Share context between Claude Code and Codex, have Claude Plan and Codex code (or vice-versa) 
- Have your agents avoid repeating the same mistakes or spending tokens overcoming the same complex problems

---

## But what actually is Forgetful?

Forgetful is an **MCP (Model Context Protocol) server** that provides persistent, semantically-searchable memory for AI agents.

Forgetful acts as shared infrastructure:
- **Protocol-level integration**: Works with Claude Code, Claude Desktop, Codex, and any MCP-compatible client
- **Semantic search**: Vector embeddings understand meaning, not just keywords
- **Knowledge graphs**: Auto-links related memories based on semantic similarity
- **Token budget management**: Protects your LLM's context window from overload

Heavily influenced by the [Zettelkasten principle](https://en.wikipedia.org/wiki/Zettelkasten): atomic memories (one concept per note) linked into knowledge graphs enable agents to recall context naturally rather than through keyword search.

---

## Key Features

- **Semantic Search with Vector Embeddings** – Find relevant context by meaning, not keywords (BAAI/bge-small-en-v1.5 model)
- **Automatic Knowledge Graphs** – Related memories auto-link during creation based on similarity thresholds
- **Multi-Resource Support** – Memories + Projects + Code Artifacts + Documents (organized hierarchy)
- **Token Budget Protection** – Configurable limits prevent context window overload (default 8K tokens)
- **Local Processing** – No external API calls; embeddings generated locally via FastEmbed
- **Flexible Storage** – SQLite (default, zero-config) or PostgreSQL (for scale and production deployments)
- **Two-Tier Retrieval** – Returns primary results + 1-hop linked memories for richer context

For the complete roadmap, see [Features Roadmap](docs/features_roadmap.md).

---

## Quick Start

### Option 1: From source (defaults to SQL Lite)

```bash
git clone https://github.com/ScottRBK/forgetful.git
cd forgetful

# Install dependencies with uv
uv sync

# Run the server (uses SQLite by default)
uv run python -m app.main
```

The server starts on `http://localhost:8020` with SQLite database (`forgetful.db`) created automatically.

### Option 2: Docker Deployment (Production/Scale)

Forgetful provides two Docker deployment options:

#### SQLite with Docker (Simpler, Single-Container)

See [docker-compose.sqlite.yml](/docker/docker-compose.sqlite.yml)

```bash
cd docker
cp .env.example .env
# Edit .env: Set DATABASE=SQLite and SQLITE_PATH=data/forgetful.db
docker compose -f docker-compose.sqlite.yml up -d
```

The SQLite database persists in the `./data` directory on the host.

#### PostgreSQL with Docker (Recommended for multitenant)

See [docker-compose.postgres.yml](/docker/docker-compose.postgres.yml) and [.env.example](/docker/.env.example)

```bash
cd docker
cp .env.example .env
# Edit .env: Set DATABASE=Postgres and configure POSTGRES_* settings
docker compose -f docker-compose.postgres.yml up -d
```

**Note**: If no `.env` file exists, the application uses defaults from `app/config/settings.py`.
For all configuration options, see [Configuration Guide](docs/configuration.md).

### Connecting to An Agent

Add Forgetful to your MCP client configuration:

```json
{
  "mcpServers": {
    "forgetful": {
      "type": "http",
      "url": "http://localhost:8020/mcp"
    }
  }
}
```

**Note**: This assumes the default server port `8020`. Adjust if you've customized `SERVER_PORT` in your `.env`.

For detailed connection guides (Claude Code, Claude Desktop, other clients that support MCP), see [Connectivity Guide](docs/connectivity_guide.md).

**WARNING:** Forgetful currently does not support authentication, so it is only advised to run this locally or on a secure local network, but don't worry though, authentication is coming :)

---

## Usage Example

### The Workflow

1. **Agent creates a memory** about an architecture decision:
   ```
   Tool: create_memory
   Title: "CI/CD preference: GitHub Actions + Docker"
   Content: "Prefer GitHub Actions for CI with Docker containerization..."
   Context: "User and I went through setting up CI/CD for a recent solution they built"
   Tags: ["preference", "cicd", "docker"]
   Importance: 9
   ```

2. **Forgetful auto-links** to related memories (existing "Docker deployment patterns", "GitHub Actions setup")

3. **Later, agent queries**: "How do I handle deployments?"
   ```
   Tool: query_memory
   Query: "deployment workflow"
   ```

4. **Forgetful retrieves**:
   - Primary result: "CI/CD preference: GitHub Actions + Docker"
   - Linked context (1-hop): "Docker deployment patterns", "GitHub Actions setup"
   - Token-budgeted results protect LLM context window

### Available MCP Tools

- `query_memory` – Semantic search across all memories
- `create_memory` – Store atomic knowledge with auto-linking
- `link_memories` – Manually connect related concepts
- `create_project` – Organize memories by context/scope
- `create_code_artifact` – Store code snippets with semantic links
- `create_document` – Store long-form content (>400 words)

For complete tool documentation, see [MCP Tools Reference](docs/connectivity_guide.md).

---

## How It Works

### Atomic Memory Principle

Inspired by Zettelkasten, each memory stores **one concept** in ~300-400 words:
- **Easily titled** – Forces clarity (200 char limit)
- **Self-contained** – Understandable without external context
- **Linkable** – Small units enable precise knowledge graphs

For detailed content, use Documents and extract 3-7 atomic memories that link to the parent document.

### Automatic Knowledge Graph

When you create a memory:
1. **Embedding generated** – FastEmbed converts content to 384-dimensional vector
2. **Similarity search** – Finds top semantically-related memories (≥0.7 threshold)
3. **Auto-linking** – Creates bidirectional links to top 3-5 matches (configurable)
4. **Graph traversal** – Queries return primary results + 1-hop linked memories

### Entities and Knowledge Graphs

Entities represent concrete, real-world things (people, organizations, teams, devices) that can be linked to memories:
  - **Typed entities** – Organizations, Individuals, Teams, Devices, or custom types
  - **Relationships** – Directional connections (e.g., "Person works_at Organization") with strength and metadata
  - **Memory linking** – Associate entities with relevant memories for context
  - **Knowledge graph** – Build networks showing how entities relate to each other and your knowledge base

Use entities for concrete things (Sarah Chen, TechFlow Systems, Cache Server 01) and memories for abstract concepts (architectural patterns, decisions, learnings).

### Token Budget Management

Prevents context window overflow:
- Configurable budget (default 8K tokens)
- Results prioritized by importance (9-10 first) → recency (newest first)
- Truncates gracefully if over budget
- Respects max memory count (default 20)

This ensures agents get the most relevant context without overwhelming the LLM.

For deep dive on search architecture (dense → sparse → RRF → cross-encoder), see [Search Documentation](docs/search.md).

---

## Configuration

**No configuration required** – Forgetful uses sensible defaults out of the box.

### Key Settings (Optional)

- `AUTH_ENABLED` – Enable authentication (default: `false`, not yet implemented)
- `MEMORY_TOKEN_BUDGET` – Max tokens for query results (default: `8000`)
- `EMBEDDING_MODEL` – Embedding model (default: `BAAI/bge-small-en-v1.5`)
- `MEMORY_NUM_AUTO_LINK` – Auto-link count (default: `3`, set `0` to disable)
- `SERVER_PORT` – HTTP server port (default: `8020`)

For all 40+ environment variables with detailed explanations, see [Configuration Guide](docs/configuration.md).

---

## Documentation

### Guides

- [Configuration Guide](docs/configuration.md) – All environment variables explained
- [Connectivity Guide](docs/connectivity_guide.md) – Connect Claude and other MCP clients
- [Search Documentation](docs/search.md) – Embedding pipeline and retrieval architecture
- [Features Roadmap](docs/features_roadmap.md) – Planned features and priorities

### External Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io/) – Model Context Protocol docs
- [pgvector](https://github.com/pgvector/pgvector) – PostgreSQL vector extension
- [FastEmbed](https://github.com/qdrant/fastembed) – Local embedding generation
- [Zettelkasten Principle](https://en.wikipedia.org/wiki/Zettelkasten) – Atomic note-taking method

---

## Contributing

We welcome contributions! Forgetful uses integration + E2E testing with Docker Compose orchestration.

See [Contributors Guide](docs/contributors.md) for:
- Testing workflows (integration tests, E2E tests, GitHub Actions)
- Development setup (local vs Docker)
- CI/CD pipeline details
- Release process

---

## License

MIT License - see [LICENSE](LICENCE.md) for details.
