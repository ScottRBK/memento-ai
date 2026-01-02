# Forgetful

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![MCP](https://img.shields.io/badge/MCP-server-purple)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![FastEmbed](https://img.shields.io/badge/FastEmbed-powered-orange)](https://github.com/qdrant/fastembed)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289da?logo=discord&logoColor=white)](https://discord.gg/ngaUjKWkFJ)


**Forgetful** is a storage and retrieval tool for AI Agents. Designed as a Model Context Protocol (MCP) server built using the FastMCP framework. Once connected to this service, MCP clients such as Coding Agents, Chat Bots or your own custom built Agents can store and retrieve information from the same knowledge base. 

![Banner](/docs/images/layers.png)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Some Examples](#usage-example)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Overview
A lot of us are using AI Agents now, especially in the realm of software development. The pace at which work and decisions are made can make it difficult for you to keep up from a notes and context persistence perspective. 

So if you are following something like the [BMAD Method](https://github.com/bmad-code-org/BMAD-METHOD) for example and you want to take your brain storming session you've just had with Claude on your desktop/mobile and use it for the basis of your next Claude Code session, then having a shared knowledge base across the two agents can help with this. 

This is just one example use case to illustrate the point, more and more agentic applications are going to surface and the use cases for sharing data across them is going to increase. 

Knowledge bases are going to become a key infrastructure component for your interactions with AIs. There are many excellent knowledge base solutions available (many for free on github) and I would encourage you to check them out and find one that works for you (even if Forgetful doesn't) as I found from personal experience that interactions with my agents got easier and more rewarding once they knew more about me, my work and previous interactions that I had had with them or other AI systems. 

What makes **Forgetful** different from other Memory based MCP services is that it is a rather opinionated view on how AI Agents such store and retrieve data.

**Forgetful** imposes the [Zettelkasten principle](https://en.wikipedia.org/wiki/Zettelkasten) when clients wish to record memories, that is each memory must be atomic (one concept per note). Along with the note (title and content), we also ask the client / agent to provide context around what it was doing when creating the note, along with keywords and tags. With this information we create semantic embeddings and store these to aid with later retrieval and in addition to this we also automatically link the memory to existing memories that have a particular similarity score, allowing for the automatic construction of a knowledge graph. 

In this sense **Forgetful** becomes a little bit like Obsidian for AI Agents, where the auto linking nudges them in building up a graph of the knowledge.

We find, [as do others (A-MEM: Agentic Memory or LLM Agents)](https://arxiv.org/abs/2502.12110), all this helps in ensuring that when the agent requires relevant information from the memory system later, the correct information is returned.

In addition to just memories, **Forgetful** also has the concept of entities (think organisation, people, products), projects, documents and code artifacts, all of which can be associated with one or more memories. 


![Architecture](docs/images/Forgetful%20Architecture.drawio_transparent.png)

## Features
- Configure either **STDIO** or **HTTP** transport mechanism (or stand up two services to support both)
- Multiple Authentication supported, flows see [FastMCP docs](https://github.com/jlowin/fastmcp/tree/main/docs/servers/auth) for full list
- Meta Tool Discovery, only three tools exposed to client application to preserve context window.
- Flexible Storage– SQLite (default, zero-config) or PostgreSQL (for scale and production deployments)
- Stores memories as vectors and allowing memories to be retrieved from natural language queries from AI.
- Cross Encoder reranking to improve recall and precision of memory retrieval. 
- Flexible ranking (embedding and cross encoder) providers, run everything locally without calls to the cloud thanks to FastEmbed
- Automatic linking of semantically similar memories, automating the creation of the knowledge graph. 

For the complete roadmap, see [Features Roadmap](docs/features_roadmap.md).

---

## Quick Start

### Option 1: PyPI (Recommended)

```bash
# Run directly with uvx (no installation needed)
uvx forgetful-ai

# Or install globally
uv tool install forgetful-ai
forgetful
```
Data stored in platform-appropriate locations (`~/.local/share/forgetful` on Linux/Mac, `AppData` on Windows).

By default, runs with stdio transport for MCP clients. For HTTP:
```bash
uvx forgetful-ai --transport http --port 8020
```

### Option 2: From Source

```bash
git clone https://github.com/ScottRBK/forgetful.git
cd forgetful

# Install dependencies with uv
uv sync

# Run the server (uses SQLite by default)
uv run main.py
```
The server starts with stdio transport. For HTTP: `uv run main.py --transport http`

### Option 3: Docker Deployment (Production/Scale)

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

For detailed connection guides (Claude Code, Claude Desktop, other clients that support MCP), see [Connectivity Guide](docs/connectivity_guide.md).

- [Claude Code](docs/connectivity_guide.md#claude-code) 
- [Cursor](docs/connectivity_guide.md#cursor) 
- [Codex](docs/connectivity_guide.md#codex) 
- [Gemini CLI](docs/connectivity_guide.md#gemini-cli) (includes [custom commands](docs/gemini-cli/README.md)) 
- [Opencode](docs/connectivity_guide.md#opencode) (includes [custom commands and skills](docs/opencode/README.md)) 

Add Forgetful to your MCP client configuration:

**stdio transport (recommended for local use):**
```json
{
  "mcpServers": {
    "forgetful": {
      "type": "stdio",
      "command": "uvx",
      "args": ["forgetful-ai"]
    }
  }
}
```

**HTTP transport (for Docker/remote):**
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


---

## Usage Examples

Forgetful exposes tools through a **meta-tools pattern** - only 3 tools visible to your MCP client, with 42 tools accessible via `execute_forgetful_tool`. See [Complete Tool Reference](docs/tool_reference.md) for all tools.

### Example 1: Project-Scoped Memory

Create a memory linked to a project for better organization and scoped retrieval.

```python
# Create project for organizing related knowledge
project = execute_forgetful_tool(
    "create_project",
    {
        "name": "E-Commerce Platform Redesign",
        "project_type": "work",
        "status": "active"
    }
)

# Create memory linked to project
memory = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Payment gateway: Stripe chosen over PayPal",
        "content": "Selected Stripe for better API docs, lower fees, and built-in fraud detection. PayPal lacks webhooks for subscription management.",
        "importance": 9,
        "tags": ["payment", "stripe", "decision"],
        "project_id": project["project_id"]
    }
)

# Later, query within project scope
results = execute_forgetful_tool(
    "query_memory",
    {
        "query": "payment processing implementation",
        "project_id": project["project_id"]
    }
)
# Returns: Stripe decision + auto-linked related memories
```

### Example 2: Knowledge Graph with Entities

Track people, organizations, and relationships - perfect for team and infrastructure management.

```python
# New engineer joins your company
new_hire = execute_forgetful_tool(
    "create_entity",
    {
        "name": "Jordan Taylor",
        "entity_type": "Individual",
        "description": "Backend Engineer - Payments Team",
        "tags": ["engineering", "backend", "payments"]
    }
)

# Get company entity (create if needed)
company = execute_forgetful_tool(
    "create_entity",
    {
        "name": "TechFlow Systems",
        "entity_type": "Organization",
        "description": "SaaS platform company"
    }
)

# Create employment relationship
execute_forgetful_tool(
    "create_entity_relationship",
    {
        "from_entity_id": new_hire["entity_id"],
        "to_entity_id": company["entity_id"],
        "relationship_type": "works_for",
        "metadata": {
            "role": "Backend Engineer II",
            "department": "Payments",
            "start_date": "2025-01-20"
        }
    }
)

# Create memory about hiring
hire_memory = execute_forgetful_tool(
    "create_memory",
    {
        "title": "Jordan Taylor hired - payments focus",
        "content": "Jordan joins to build Stripe integration and handle PCI compliance. Previous experience with payment systems at FinanceApp Corp.",
        "importance": 7,
        "tags": ["team", "hiring", "payments"]
    }
)

# Link person to memory
execute_forgetful_tool(
    "link_entity_to_memory",
    {
        "entity_id": new_hire["entity_id"],
        "memory_id": hire_memory["memory_id"]
    }
)

# Query Jordan's related knowledge
results = execute_forgetful_tool(
    "query_memory",
    {"query": "Jordan payment implementation"}
)
# Returns: Hiring memory + linked entity + relationship context
```

### Tool Categories

Forgetful provides **42 tools** across **6 categories**:

- **Memory Tools** (7) – create, query, update, link, mark obsolete
- **Project Tools** (5) – organize knowledge by context/scope
- **Entity Tools** (15) – track people, orgs, devices; build knowledge graphs
- **Code Artifact Tools** (5) – store reusable code snippets
- **Document Tools** (5) – store long-form content (>400 words)
- **User Tools** (2) – profile and authentication

For complete documentation with extensive examples, see [Complete Tool Reference](docs/tool_reference.md).

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

- `MEMORY_TOKEN_BUDGET` – Max tokens for query results (default: `8000`)
- `EMBEDDING_MODEL` – Embedding model (default: `BAAI/bge-small-en-v1.5`)
- `MEMORY_NUM_AUTO_LINK` – Auto-link count (default: `3`, set `0` to disable)
- `SERVER_PORT` – HTTP server port (default: `8020`)

For all 40+ environment variables with detailed explanations, see [Configuration Guide](docs/configuration.md).

---

## Documentation

### Guides

- **[Core Concepts](docs/concepts.md)** – Memories vs Entities vs Documents explained
- **[Complete Tool Reference](docs/tool_reference.md)** – All 42 tools with extensive examples
- **[REST API Reference](docs/api_reference.md)** – HTTP endpoints for web UI integration
- [Configuration Guide](docs/configuration.md) – All environment variables explained
- [Connectivity Guide](docs/connectivity_guide.md) – Connect Claude and other MCP clients
- [Self-Hosting Guide](docs/self-hosting-guide.md) – Deploy on a VPS with Docker
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
