# Gemini CLI Commands for Forgetful

Custom commands for using Forgetful with [Gemini CLI](https://github.com/google-gemini/gemini-cli).

> **Credits**: These commands were contributed by [@CharlieBytesX](https://github.com/CharlieBytesX) in [Discussion #15](https://github.com/ScottRBK/forgetful/discussions/15).

## Prerequisites

Ensure Forgetful MCP server is configured:

```bash
# STDIO transport (recommended for local use)
gemini mcp add forgetful uvx forgetful-ai

# Or HTTP transport (for remote/Docker)
gemini mcp add -t http forgetful http://localhost:8020/mcp
```

## Installation

Copy all commands to your Gemini CLI commands directory:

```bash
cp docs/gemini-cli/commands/*.toml ~/.gemini/commands/
```

Or copy individual commands as needed.

## Available Commands

| Command | Description |
|---------|-------------|
| `/encode-repo` | Bootstrap a repository into Forgetful's knowledge base using a 7-phase protocol |
| `/forgetful-setup` | Configure the Forgetful MCP server |
| `/memory-explore` | Deep exploration of the Forgetful knowledge graph |
| `/memory-list` | List recent memories from Forgetful |
| `/memory-save` | Save current context as an atomic memory with curation workflow |
| `/memory-search` | Search memories semantically |

## Usage Examples

### Encode a Repository

Bootstrap a new project into Forgetful:

```
/encode-repo my-project
```

The command walks through 7 phases: discovery, foundation, architecture, patterns, features, decisions, and validation.

### Save a Memory

After a conversation where you learned something important:

```
/memory-save
```

The command will analyze the conversation, check for existing related memories, and propose a new atomic memory with proper curation.

### Search Memories

Find relevant context from your knowledge base:

```
/memory-search authentication patterns
```

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

## Command Format

Gemini CLI commands are TOML files supporting:

- `{{args}}` - Argument injection from user input
- `@{path}` - File content injection
- `!{command}` - Shell command output injection

See the [Gemini CLI documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/custom-commands.md) for more details.
