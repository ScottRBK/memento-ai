# OpenCode Integration for Forgetful

Custom commands and skills for using Forgetful with [OpenCode](https://opencode.ai).

## Prerequisites

Ensure you have:
- [OpenCode](https://opencode.ai) installed
- [uvx](https://docs.astral.sh/uv/concepts/tools/) available (comes with uv)

## MCP Server Configuration

Add Forgetful to your OpenCode configuration file (`opencode.json` or `opencode.jsonc`):

### Standard Setup (Recommended)

Zero-config setup using SQLite storage:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "forgetful": {
      "type": "local",
      "command": ["uvx", "forgetful-ai"],
      "enabled": true
    }
  }
}
```

Your memories will persist in `~/.forgetful/forgetful.db`.

### Custom Setup (Advanced)

For PostgreSQL, custom embeddings, or remote servers:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "forgetful": {
      "type": "local",
      "command": ["uvx", "forgetful-ai"],
      "enabled": true,
      "environment": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/forgetful",
        "EMBEDDING_PROVIDER": "Google",
        "EMBEDDING_MODEL": "models/text-embedding-001"
      }
    }
  }
}
```

### Remote HTTP Server

For connecting to a Forgetful instance running elsewhere:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "forgetful": {
      "type": "remote",
      "url": "http://localhost:8020/mcp",
      "enabled": true,
    }
  }
}
```

See [configuration.md](../configuration.md) for all available environment variables.

## Installation

### Commands

Copy command files to your OpenCode commands directory:

```bash
# Global installation
cp docs/opencode/commands/*.md ~/.config/opencode/command/

# Or project-specific
cp docs/opencode/commands/*.md .opencode/command/
```

### Skills

Copy skill folders to your OpenCode skills directory:

```bash
# Global installation
cp -r docs/opencode/skills/* ~/.config/opencode/skill/

# Or project-specific
cp -r docs/opencode/skills/* .opencode/skill/
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/forgetful-setup` | Configure the Forgetful MCP server |
| `/memory-search` | Search memories semantically |
| `/memory-save` | Save current context as an atomic memory with curation workflow |
| `/memory-list` | List recent memories from Forgetful |
| `/memory-explore` | Deep exploration of the Forgetful knowledge graph |
| `/encode-repo` | Bootstrap a repository into Forgetful's knowledge base |

## Available Skills

Skills are automatically discovered by OpenCode and loaded on-demand via the `skill` tool.

| Skill | Description |
|-------|-------------|
| `using-forgetful-memory` | Guidance for effective memory usage with Zettelkasten principles |
| `curating-memories` | Maintain memory quality through updates, obsolescence, and linking |
| `exploring-knowledge-graph` | Deep knowledge graph traversal for comprehensive context |

## Usage Examples

### Search Memories

Find relevant context from your knowledge base:

```
/memory-search authentication patterns
```

### Save a Memory

After a conversation with important insights:

```
/memory-save
```

The command analyzes the conversation, checks for related memories, and proposes an atomic memory with proper curation.

### List Recent Memories

See what's been added recently:

```
/memory-list 10
```

### Explore the Knowledge Graph

Deep traversal of related memories, entities, and documents:

```
/memory-explore payment processing
```

### Encode a Repository

Bootstrap a new project into Forgetful:

```
/encode-repo my-project
```

## Command Format

OpenCode commands are Markdown files with YAML frontmatter:

```markdown
---
description: Brief description shown in TUI
---
Template text with $ARGUMENTS placeholder
```

Supported placeholders:
- `$ARGUMENTS` - All passed arguments combined
- `$1`, `$2`, `$3` - Individual positional arguments
- `` !`command` `` - Shell command output injection
- `@path/to/file` - File content injection

See the [OpenCode commands documentation](https://opencode.ai/docs/commands/) for more details.

## Skill Format

OpenCode skills are `SKILL.md` files in named folders:

```markdown
---
name: skill-name
description: What the skill does and when to use it
---
# Skill Content
Detailed guidance for the agent...
```

See the [OpenCode skills documentation](https://opencode.ai/docs/skills/) for more details.

## Troubleshooting

### MCP Server Not Found

Verify uvx is installed:
```bash
which uvx
```

If not found, install uv: https://docs.astral.sh/uv/getting-started/installation/

### Connection Timeout

Increase the timeout in your configuration:
```jsonc
{
  "mcp": {
    "forgetful": {
      "type": "local",
      "command": ["uvx", "forgetful-ai"],
      "timeout": 60000
    }
  }
}
```

### Check Server Status

For HTTP servers, verify the endpoint is accessible:
```bash
curl http://localhost:8020/health
```

### View Logs

Check Forgetful logs at `~/.forgetful/forgetful.log` (if logging is enabled).
