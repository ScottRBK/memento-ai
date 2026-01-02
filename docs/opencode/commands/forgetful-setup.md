---
description: Configure Forgetful MCP server for OpenCode
---
# Forgetful Setup

Configure the Forgetful semantic memory MCP server for OpenCode.

## Step 1: Check Existing Configuration

First, check if Forgetful is already configured in your `opencode.json`:

```bash
!`cat opencode.json 2>/dev/null | grep -A5 forgetful || echo "Not configured"`
```

If already configured:
- Ask user if they want to reconfigure
- If no, exit with message: "Forgetful is already configured."
- If yes, proceed to modify the configuration

## Step 2: Choose Setup Type

Ask the user which setup they prefer:

**Question**: "How would you like to configure Forgetful?"

**Options**:
1. **Standard (Recommended)** - Zero config, uses uvx to run Forgetful with SQLite storage. Perfect for most users.
2. **Custom** - For advanced setups: remote HTTP server, PostgreSQL, custom embeddings, authentication, etc.

## Step 3a: Standard Setup

If user chose Standard, add this to their `opencode.json`:

```jsonc
{
  "mcp": {
    "forgetful": {
      "type": "local",
      "command": ["uvx", "forgetful-ai"],
      "enabled": true
    }
  }
}
```

Report: "Forgetful is now configured! Your memories will persist in `~/.forgetful/` using SQLite. Restart OpenCode to activate."

## Step 3b: Custom Setup

If user chose Custom:

1. Fetch the configuration docs:
```
WebFetch: https://github.com/ScottRBK/forgetful/blob/main/docs/configuration.md
```

2. Ask what they need:
   - **Remote HTTP server** - Connect to Forgetful running elsewhere
   - **PostgreSQL backend** - Use Postgres instead of SQLite
   - **Custom embeddings** - Use different embedding model/provider
   - **Authentication** - API key or OAuth setup

3. Based on their answers, build the appropriate configuration:

**For HTTP remote server:**
```jsonc
{
  "mcp": {
    "forgetful": {
      "type": "remote",
      "url": "http://HOST:PORT/mcp",
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

**For PostgreSQL with custom embeddings:**
```jsonc
{
  "mcp": {
    "forgetful": {
      "type": "local",
      "command": ["uvx", "forgetful-ai"],
      "enabled": true,
      "environment": {
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/forgetful",
        "EMBEDDING_PROVIDER": "Google",
        "EMBEDDING_MODEL": "models/text-embedding-004"
      }
    }
  }
}
```

4. Help the user update their `opencode.json` with the configuration.

## Troubleshooting

If setup fails:
- Check if `uvx` is installed: `which uvx`
- For HTTP: verify the server is running and accessible
- Restart OpenCode after configuration changes

## Notes

- SQLite database location: `~/.forgetful/forgetful.db`
- For full configuration reference: https://github.com/ScottRBK/forgetful/blob/main/docs/configuration.md
