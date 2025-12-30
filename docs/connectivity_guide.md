This section provides more detailed instructions on how to connect forgetful to various AI Agent applications.
- [Claude Code](#claude-code) 
- [Cursor](#cursor) 
- [Codex](#codex) 
- [Gemini CLI](#gemini-cli) 

## Claude Code

### [Plugin](https://github.com/ScottRBK/forgetful-plugin) 

```bash
/plugin marketplace add ScottRBK/forgetful-plugin
/plugin install forgetful-plugin@forgetful-plugins
cd ~/.claude/plugins/forgetful-plugin
cp .mcp.json.stdio.example .mcp.json
```


### STDIO Transport
```bash
claude mcp add --scope user forgetful uvx forgetful-ai
```

### STDIO with Environment Variables
```bash
claude mcp add --scope user forgetful uvx forgetful-ai \
  -e DATABASE_URL=postgresql://user:pass@localhost:5432/forgetful \
  -e EMBEDDING_PROVIDER=Google \
  -e EMBEDDING=models/gemini-embedding-001 \
  -e GOOGLE_AI_API_KEY=your-api-key
```

### HTTP Transport 
```bash
claude mcp add --transport http --scope user forgetful http://localhost:8020/mcp
```


## Cursor
Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file is the recommended approach. You may also install in a specific project by creating `.cursor/mcp.json` in your project folder. See [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol) for more info.


### STDIO Transport

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

### HTTP Transport
```json
{
  "mcpServers": {
    "forgetful": {
      "url": "http://localhost:8020/mcp"
      }
    }
}
```

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=forgetful_ai&config=eyJjb21tYW5kIjoidXZ4IGZvcmdldGZ1bC1haSJ9)


## Codex

### STDIO Transport

```bash
codex mcp add forgetful uvx forgetful-ai 
```

### HTTP Transport

```bash
codex mcp add forgetful --url http://localhost:8020/mcp
```



## Gemini CLI

### STDIO Transport

```bash
gemini mcp add forgetful uvx forgetful-ai
```
### HTTP Transport

```bash
gemini mcp add -t http forgetful http://localhost:8020/mcp
```

### Custom Commands

For enhanced workflows with Forgetful, we provide ready-to-use Gemini CLI commands for memory management, search, and repository encoding.

See [Gemini CLI Commands](gemini-cli/README.md) for installation and usage.


