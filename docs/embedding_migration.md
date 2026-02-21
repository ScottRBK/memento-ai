# Embedding Provider Migration

When you switch embedding providers or models (e.g., from FastEmbed to OpenAI, or from `bge-small-en-v1.5` to `text-embedding-3-small`), existing memory embeddings become incompatible. Different providers produce vectors with different dimensions and semantic spaces, so a search query embedded with the new provider won't match memories embedded with the old one.

Forgetful includes a built-in CLI tool to handle this migration safely.

---

## When You Need to Re-embed

You need to run a re-embedding migration whenever you change any of these settings:

| Setting | Example Change |
|---------|---------------|
| `EMBEDDING_PROVIDER` | `FastEmbed` -> `OpenAI` |
| `EMBEDDING_MODEL` | `bge-small-en-v1.5` -> `text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | `384` -> `1536` |

If you only change non-embedding settings (database, auth, reranking, etc.), no re-embedding is needed.

---

## Quick Start

```bash
# 1. Update your .env with the new provider settings
EMBEDDING_PROVIDER=OpenAI
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
OPENAI_API_KEY=sk-...

# 2. Preview what will happen (no changes made)
forgetful --re-embed --dry-run

# 3. Run the migration
forgetful --re-embed
```

If running from source:

```bash
uv run main.py --re-embed --dry-run
uv run main.py --re-embed
```

---

## CLI Reference

### `--re-embed`

Runs the re-embedding migration instead of starting the server. Processes all memories with the currently configured embedding provider.

```bash
forgetful --re-embed [--batch-size N] [--dry-run]
```

### `--batch-size N`

Number of memories to process per batch. Default: `20`.

Lower values use less memory and are safer for rate-limited APIs. Higher values are faster for local providers like FastEmbed.

```bash
forgetful --re-embed --batch-size 50    # faster for local providers
forgetful --re-embed --batch-size 5     # conservative for rate-limited APIs
```

### `--dry-run`

Shows configuration and memory count without making any changes. Use this to verify your setup before committing to a migration.

```bash
forgetful --re-embed --dry-run
```

Output:

```
[1/5] Validating configuration...
  Provider: OpenAI (text-embedding-3-small)
  Dimensions: 1536
  Database: SQLite (/home/user/.local/share/forgetful/forgetful.db)
  Batch size: 20
  Memories to process: 127

[DRY RUN] Would re-embed 127 memories with the above configuration.
  No changes were made.
```

---

## What Happens During Migration

The tool follows a 5-step process:

### Step 1: Validate Configuration

Displays the target provider, model, dimensions, database backend, and memory count. Confirms the settings are what you intend before proceeding.

### Step 2: Create Backup

Creates a timestamped backup of your database:

- **SQLite**: Copies the `.db` file (plus WAL/SHM if present) to `forgetful.db.bak-YYYYMMDD-HHMMSS`
- **PostgreSQL**: Runs `pg_dump` to `forgetful-pg-YYYYMMDD-HHMMSS.sql`

The backup is kept alongside your database. In-memory SQLite databases skip this step.

### Step 3: Update Vector Schema

Resizes the vector storage to match the new `EMBEDDING_DIMENSIONS`:

- **SQLite**: Drops and recreates the `vec_memories` virtual table
- **PostgreSQL**: Alters the `embedding` column type to `vector(N)`

### Step 4: Re-embed Memories

Processes all memories in batches:
1. Reads a batch of memories from the database
2. Generates new embeddings using the configured provider
3. Writes the new embeddings back
4. Reports progress via a live progress bar

```
[4/5] Re-embedding memories...
  [████████████████████░░░░░] 102/127 memories (80%)
```

### Step 5: Validate

Runs three automated checks:

1. **Count check** - Verifies every memory has an embedding
2. **Dimension check** - Samples embeddings and confirms correct dimension count
3. **Search check** - Runs a smoke-test semantic search to confirm results are returned

```
[5/5] Validating...
  Count check: 127 memories, 127 embeddings ✓
  Dimension check: ✓
  Search check: ✓
```

---

## Failure Handling

The tool is designed to be safe. If anything goes wrong, your database is automatically restored.

### Automatic Restore

The backup is restored automatically in these scenarios:

- **Embedding API error** (rate limit, network failure, invalid key)
- **Validation failure** (count mismatch, dimension mismatch, broken search)
- **Interrupt signal** (Ctrl+C / SIGTERM)

```
[4/5] Re-embedding memories...
  [████░░░░░░░░░░░░░░░░░░░░░] 8/127 memories (6%)
  ERROR: OpenAI API rate limit exceeded

  Restoring from backup...
  Restored: /home/user/.local/share/forgetful/forgetful.db.bak-20260220-143022
  Database returned to pre-migration state.
```

### Manual Restore

If you need to manually restore after a successful migration (e.g., you notice search quality issues):

**SQLite:**
```bash
# The backup path is printed at the end of the migration
cp /path/to/forgetful.db.bak-YYYYMMDD-HHMMSS /path/to/forgetful.db
```

**PostgreSQL:**
```bash
psql -h localhost -p 5099 -U forgetful -d forgetful -f /path/to/forgetful-pg-YYYYMMDD-HHMMSS.sql
```

### Backup Cleanup

Backups are retained after a successful migration. Delete them manually once you're satisfied:

```bash
rm /path/to/forgetful.db.bak-*          # SQLite
rm /path/to/forgetful-pg-*.sql          # PostgreSQL
```

---

## Common Migration Scenarios

### FastEmbed (local) to OpenAI (cloud)

```bash
# .env
EMBEDDING_PROVIDER=OpenAI
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
OPENAI_API_KEY=sk-...

# Migrate
forgetful --re-embed --batch-size 20
```

### FastEmbed to Ollama (local)

```bash
# .env
EMBEDDING_PROVIDER=Ollama
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768

# Migrate
forgetful --re-embed --batch-size 50
```

### OpenAI to Azure OpenAI

```bash
# .env
EMBEDDING_PROVIDER=Azure
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSIONS=1536
AZURE_ENDPOINT=https://my-resource.openai.azure.com/
AZURE_DEPLOYMENT=text-embedding-ada-002
AZURE_API_VERSION=2023-05-15
AZURE_API_KEY=...

# Migrate (same dimensions, but different provider = different vector space)
forgetful --re-embed
```

### Upgrading Model Within Same Provider

Even when staying on the same provider, switching models requires re-embedding:

```bash
# .env - switching from small to large model
EMBEDDING_PROVIDER=OpenAI
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072
OPENAI_API_KEY=sk-...

# Migrate
forgetful --re-embed
```

---

## Docker Deployments

For Docker-based deployments, run the re-embed command inside the container:

### Docker Compose

```bash
# SQLite
docker compose exec forgetful-service python main.py --re-embed --dry-run
docker compose exec forgetful-service python main.py --re-embed

# PostgreSQL
docker compose exec forgetful-service python main.py --re-embed --dry-run
docker compose exec forgetful-service python main.py --re-embed
```

Make sure your updated `.env` is mounted in the container before running.

### PostgreSQL Backup Requirements

For PostgreSQL backups to work in Docker, the container needs `pg_dump` and `psql` available. The standard Forgetful Docker image includes these tools. If using a custom image, ensure the PostgreSQL client tools are installed.

---

## Tips

- **Always dry-run first** to verify your configuration and memory count
- **Use a conservative batch size** (10-20) for cloud providers to avoid rate limits
- **Use a larger batch size** (50-100) for local providers (FastEmbed, Ollama) for faster processing
- **Don't delete backups immediately** - verify search quality first by querying a few memories
- **Stop the server** before running re-embed to avoid concurrent access issues
- The migration processes all users' memories in a single run (it's a global operation)

---

## Further Reading

- [Configuration Guide](./configuration.md) - All embedding provider settings
- [Search Documentation](./search.md) - How embeddings are used in search
- [Self-Hosting Guide](./self-hosting-guide.md) - Deployment and backup strategies
