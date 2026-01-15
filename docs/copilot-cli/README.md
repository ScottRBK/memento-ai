# GitHub Copilot CLI Integration for Forgetful

Custom agents and skills for using Forgetful with [GitHub Copilot CLI](https://github.com/github/copilot-cli).

## Prerequisites

Ensure you have:
- [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli) installed
- A GitHub Copilot subscription (Pro, Pro+, Business, or Enterprise)
- [uvx](https://docs.astral.sh/uv/concepts/tools/) available (comes with uv)

## MCP Server Configuration

### Standard Setup (Recommended)

Add Forgetful via the interactive `/mcp add` command in Copilot CLI:

```bash
# Start Copilot CLI
copilot

# Then use the /mcp add command
/mcp add
# Enter the following:
#   Name: forgetful
#   Command: uvx
#   Arguments: forgetful-ai
# Press Ctrl+S to save
```

Your memories will persist in `~/.forgetful/forgetful.db`.

### Manual Configuration

Alternatively, edit `~/.copilot/mcp-config.json` directly:

```json
{
  "mcpServers": {
    "forgetful": {
      "command": "uvx",
      "args": ["forgetful-ai"]
    }
  }
}
```

### Custom Setup (Advanced)

For PostgreSQL, custom embeddings, or environment variables:

```json
{
  "mcpServers": {
    "forgetful": {
      "command": "uvx",
      "args": ["forgetful-ai"],
      "env": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/forgetful",
        "EMBEDDING_PROVIDER": "Google",
        "EMBEDDING_MODEL": "models/text-embedding-004"
      }
    }
  }
}
```

### Remote HTTP Server

For connecting to a Forgetful instance running elsewhere:

```json
{
  "mcpServers": {
    "forgetful": {
      "url": "http://localhost:8020/mcp"
    }
  }
}
```

See [configuration.md](../configuration.md) for all available environment variables.

## Installation

### Agents

Copy agent files to your Copilot CLI agents directory:

```bash
# Global installation (all projects)
cp docs/copilot-cli/agents/*.agent.md ~/.copilot/agents/

# Or repository-specific
mkdir -p .github/agents
cp docs/copilot-cli/agents/*.agent.md .github/agents/
```

### Skills

Copy skill folders to your Copilot CLI skills directory:

```bash
# Global installation (all projects)
cp -r docs/copilot-cli/skills/* ~/.copilot/skills/

# Or repository-specific
mkdir -p .github/skills
cp -r docs/copilot-cli/skills/* .github/skills/
```

## Available Agents

Custom agents are specialized versions of Copilot for specific tasks. Invoke them via `/agent` or let Copilot route automatically based on your prompt.

| Agent | Description |
|-------|-------------|
| `forgetful-memory` | Memory operations: search, save, update, and manage memories |
| `memory-curator` | Memory maintenance: deduplicate, link, mark obsolete, update |
| `knowledge-explorer` | Deep knowledge graph traversal for comprehensive context |

## Available Skills

Skills provide on-demand guidance that Copilot loads when relevant to your task.

| Skill | Description |
|-------|-------------|
| `using-forgetful-memory` | Guidance for effective memory usage with Zettelkasten principles |
| `curating-memories` | Maintain memory quality through updates, obsolescence, and linking |
| `exploring-knowledge-graph` | Deep knowledge graph traversal for comprehensive context |

## Usage Examples

### Search Memories

Using natural language (Copilot routes automatically):

```
Search my memories for authentication patterns
```

Or explicitly invoke the agent:

```
/agent forgetful-memory
Search for authentication patterns in my knowledge base
```

### Save a Memory

After a conversation with important insights:

```
Save this conversation about the new caching strategy to memory with importance 8
```

### List Recent Memories

```
Show me the last 10 memories from the Forgetful project
```

### Explore the Knowledge Graph

```
/agent knowledge-explorer
Trace all connections from the payment processing decision
```

### Encode a Repository

Bootstrap a new project into Forgetful:

```
Analyze this repository and create a project in Forgetful with key architectural decisions and patterns as memories
```

## Agent Format

GitHub Copilot CLI agents are Markdown files with YAML frontmatter:

```markdown
---
name: agent-name
description: Brief description (required)
tools: ["tool1", "tool2"]  # Optional, omit for all tools
---
# Agent Instructions

Detailed behavioral guidance for the agent...
```

**Storage locations:**
- Global: `~/.copilot/agents/`
- Repository: `.github/agents/`

**Filename format:** `agent-name.agent.md`

See the [Custom Agents documentation](https://docs.github.com/en/copilot/reference/custom-agents-configuration) for more details.

## Skill Format

GitHub Copilot CLI skills use `SKILL.md` files in named folders:

```markdown
---
name: skill-name
description: What the skill does and when to use it
---
# Skill Content

Detailed guidance for the agent...
```

**Storage locations:**
- Global: `~/.copilot/skills/`
- Repository: `.github/skills/`

See the [Agent Skills documentation](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) for more details.

## Troubleshooting

### MCP Server Not Found

Verify uvx is installed:
```bash
which uvx
```

If not found, install uv: https://docs.astral.sh/uv/getting-started/installation/

### Check MCP Configuration

List configured MCP servers:
```bash
# In Copilot CLI session
/mcp list
```

Or check the config file directly:
```bash
cat ~/.copilot/mcp-config.json
```

### Connection Issues

For HTTP servers, verify the endpoint is accessible:
```bash
curl http://localhost:8020/health
```

### View Logs

Check Forgetful logs at `~/.forgetful/forgetful.log` (if logging is enabled).

### Agent Not Loading

Ensure agent files have the correct extension (`.agent.md`) and are in the right location:
```bash
ls ~/.copilot/agents/
ls .github/agents/
```
