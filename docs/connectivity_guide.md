This section provides more detailed instructions on how to connect forgetful to various AI Agent applications.


<detail>
<summary><b>Claude Code</b></summary>

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

</detail>

<detail>
<summary><b>Cursor</b></summary>

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
}

```

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=forgetful_ai&config=eyJjb21tYW5kIjoidXZ4IGZvcmdldGZ1bC1haSJ9)
</detail>

<detail>
<summary><b>Codex</b></summary>



### STDIO Transport

```bash
codex mcp add forgetful uvx forgetful-ai 
```

### HTTP Transport

```bash
codex mcp add forgetful --url http://localhost:8020/mcp
```

</detail>


<detail>
<summary><b>Gemini CLI</summary>

### STDIO Transport

```bash
gemini mcp add forgetful uvx forgetful-ai
```
### HTTP Transport

```bash
gemini mcp add -t http forgetful http://localhost:8020/mcp
```


</detail>
