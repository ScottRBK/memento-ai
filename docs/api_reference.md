# REST API Reference

Forgetful exposes a REST API for web UI integration and external access.

**Base URL:** `http://localhost:8020/api/v1`

## Authentication

The REST API uses the **same authentication provider** as MCP routes. This means:

- If you've configured OAuth2/OIDC for MCP, the same tokens work for REST
- If auth is disabled (`FASTMCP_SERVER_AUTH` not set), REST endpoints use a default user
- All FastMCP auth providers are supported (JWT, OAuth2, GitHub, Google, Azure, etc.)

### When Auth is Enabled

Include a Bearer token in the Authorization header:

```
Authorization: Bearer <your-oauth-token>
```

The token is validated using `mcp.auth.verify_token()` - the same mechanism used for MCP tool authentication. User identity is extracted from the token's `sub` claim.

### When Auth is Disabled (Default)

If `FASTMCP_SERVER_AUTH` is not set, all requests use a default user. No Authorization header is required.

### Configuration

Authentication is configured via FastMCP environment variables:

```bash
# Example: GitHub OAuth
FASTMCP_SERVER_AUTH=github
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

# Example: Bearer token (simple API key)
FASTMCP_SERVER_AUTH=bearer
FASTMCP_SERVER_AUTH_SECRET=your-secret-key
```

See [FastMCP Auth Documentation](https://fastmcp.wiki/en/servers/auth/authentication) for all supported providers and configuration options.

## Common Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Health

### GET /health

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-12-05T10:00:00Z",
  "service": "forgetful",
  "version": "0.3.0"
}
```

---

## Memories

### GET /api/v1/memories

List memories with pagination, sorting, and filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Results per page (1-100) |
| `offset` | int | 0 | Skip N results |
| `sort_by` | string | created_at | Sort field: `created_at`, `updated_at`, `importance` |
| `sort_order` | string | desc | Sort direction: `asc`, `desc` |
| `project_id` | int | - | Filter by project |
| `importance_min` | int | - | Minimum importance (1-10) |
| `tags` | string | - | Comma-separated tags |
| `include_obsolete` | bool | false | Include obsolete memories |

**Response:**
```json
{
  "memories": [
    {
      "id": 1,
      "title": "Memory title",
      "content": "Memory content...",
      "importance": 7,
      "tags": ["tag1", "tag2"],
      "created_at": "2024-12-05T10:00:00Z",
      "updated_at": "2024-12-05T10:00:00Z",
      "linked_memory_ids": [2, 3],
      "project_ids": [1],
      "source_repo": "owner/repo",
      "source_files": ["path/to/file.py"],
      "source_url": "https://example.com/source",
      "confidence": 0.85,
      "encoding_agent": "claude-sonnet-4",
      "encoding_version": "1.0.0"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### GET /api/v1/memories/{id}

Get a single memory by ID.

**Response:** Memory object (see above)

### POST /api/v1/memories

Create a new memory.

**Request Body:**
```json
{
  "title": "Memory title",
  "content": "Memory content...",
  "context": "Why this is being stored",
  "keywords": ["keyword1", "keyword2"],
  "tags": ["tag1"],
  "importance": 7,
  "project_id": 1,
  "source_repo": "owner/repo",
  "source_files": ["path/to/file.py"],
  "source_url": "https://example.com/source",
  "confidence": 0.85,
  "encoding_agent": "claude-sonnet-4",
  "encoding_version": "1.0.0"
}
```

**Provenance Fields (all optional):**

| Field | Type | Description |
|-------|------|-------------|
| `source_repo` | string | Repository source (e.g., 'owner/repo', max 200 chars) |
| `source_files` | string[] | List of file paths that informed this memory |
| `source_url` | string | URL to original source material (max 2048 chars) |
| `confidence` | float | Encoding confidence score (0.0-1.0) |
| `encoding_agent` | string | Agent/process that created this memory (max 100 chars) |
| `encoding_version` | string | Version of encoding process/prompt (max 50 chars) |

**Response (201):**
```json
{
  "id": 1,
  "title": "Memory title",
  "linked_memory_ids": [],
  "project_ids": [1],
  "code_artifact_ids": [],
  "document_ids": [],
  "similar_memories": []
}
```

### PUT /api/v1/memories/{id}

Update an existing memory.

**Request Body:** (all fields optional)
```json
{
  "title": "Updated title",
  "content": "Updated content",
  "importance": 8,
  "tags": ["updated-tag"],
  "source_repo": "owner/repo",
  "source_files": ["path/to/file.py"],
  "source_url": "https://example.com/source",
  "confidence": 0.9,
  "encoding_agent": "manual-review",
  "encoding_version": "1.0.0"
}
```

Provenance fields can be added or updated after memory creation. See POST /api/v1/memories for field descriptions.

**Response:** Updated memory object

### DELETE /api/v1/memories/{id}

Mark a memory as obsolete (soft delete).

**Request Body:** (optional)
```json
{
  "reason": "No longer relevant",
  "superseded_by": 42
}
```

**Response:**
```json
{
  "success": true
}
```

### POST /api/v1/memories/search

Semantic search across memories.

**Request Body:**
```json
{
  "query": "search query",
  "query_context": "why searching",
  "k": 10,
  "include_links": true,
  "importance_threshold": 5,
  "project_ids": [1, 2]
}
```

**Response:**
```json
{
  "memories": [...],
  "total": 10
}
```

### POST /api/v1/memories/{id}/links

Link memories together (bidirectional).

**Request Body:**
```json
{
  "related_ids": [2, 3, 4]
}
```

**Response:**
```json
{
  "linked_ids": [2, 3, 4]
}
```

### GET /api/v1/memories/{id}/links

Get memories linked to this memory.

**Query Parameters:**
- `limit` (int, default 20): Max linked memories to return

**Response:**
```json
{
  "memory_id": 1,
  "linked_memories": [...]
}
```

### DELETE /api/v1/memories/{id}/links/{target_id}

Remove a link between two memories (bidirectional).

**Response:**
```json
{
  "success": true
}
```

---

## Projects

### GET /api/v1/projects

List all projects.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `active`, `archived`, `completed` |
| `repo_name` | string | Filter by repository name |

**Response:**
```json
{
  "projects": [
    {
      "id": 1,
      "name": "Project Name",
      "description": "Project description",
      "project_type": "development",
      "status": "active",
      "repo_name": "owner/repo",
      "created_at": "2024-12-05T10:00:00Z"
    }
  ],
  "total": 5
}
```

### GET /api/v1/projects/{id}

Get a single project by ID.

### POST /api/v1/projects

Create a new project.

**Request Body:**
```json
{
  "name": "Project Name",
  "description": "Project description",
  "project_type": "development",
  "repo_name": "owner/repo"
}
```

**Project Types:** `personal`, `work`, `learning`, `development`, `infrastructure`, `template`, `product`, `documentation`, `open-source`

### PUT /api/v1/projects/{id}

Update an existing project.

**Request Body:** (all fields optional)
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "status": "completed"
}
```

### DELETE /api/v1/projects/{id}

Delete a project (preserves associated memories).

---

## Entities

### GET /api/v1/entities

List all entities.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_type` | string | Filter by type: `Individual`, `Organization`, `Team`, `Device`, `Other` |

**Response:**
```json
{
  "entities": [
    {
      "id": 1,
      "name": "Entity Name",
      "entity_type": "Individual",
      "custom_type": null,
      "notes": "Some notes",
      "created_at": "2024-12-05T10:00:00Z"
    }
  ],
  "total": 10
}
```

### GET /api/v1/entities/{id}

Get a single entity by ID.

### POST /api/v1/entities

Create a new entity.

**Request Body:**
```json
{
  "name": "Entity Name",
  "entity_type": "Individual",
  "custom_type": "Custom Type (if entity_type is Other)",
  "notes": "Optional notes"
}
```

### PUT /api/v1/entities/{id}

Update an existing entity.

### DELETE /api/v1/entities/{id}

Delete an entity.

### POST /api/v1/entities/search

Search entities by name.

**Request Body:**
```json
{
  "query": "search term",
  "entity_type": "Individual",
  "limit": 10
}
```

### POST /api/v1/entities/{id}/memories

Link an entity to a memory.

**Request Body:**
```json
{
  "memory_id": 1
}
```

### DELETE /api/v1/entities/{id}/memories/{memory_id}

Remove link between entity and memory.

### GET /api/v1/entities/{id}/relationships

Get relationships for an entity.

**Response:**
```json
{
  "relationships": [
    {
      "id": 1,
      "source_entity_id": 1,
      "target_entity_id": 2,
      "relationship_type": "manages",
      "description": "Team lead"
    }
  ],
  "total": 3
}
```

### POST /api/v1/entities/{id}/relationships

Create a relationship between entities.

**Request Body:**
```json
{
  "target_entity_id": 2,
  "relationship_type": "manages",
  "description": "Optional description"
}
```

### PUT /api/v1/entities/relationships/{id}

Update an entity relationship.

### DELETE /api/v1/entities/relationships/{id}

Delete an entity relationship.

---

## Documents

### GET /api/v1/documents

List all documents.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | int | Filter by project |
| `document_type` | string | Filter by type |
| `tags` | string | Comma-separated tags |

**Response:**
```json
{
  "documents": [
    {
      "id": 1,
      "title": "Document Title",
      "description": "Brief description",
      "content": "Full document content...",
      "document_type": "analysis",
      "tags": ["tag1"],
      "created_at": "2024-12-05T10:00:00Z"
    }
  ],
  "total": 5
}
```

**Document Types:** `analysis`, `guide`, `specification`, `report`, `note`, `reference`

### GET /api/v1/documents/{id}

Get a single document by ID.

### POST /api/v1/documents

Create a new document.

**Request Body:**
```json
{
  "title": "Document Title",
  "description": "Brief description",
  "content": "Full document content...",
  "document_type": "analysis",
  "tags": ["tag1"]
}
```

### PUT /api/v1/documents/{id}

Update an existing document.

### DELETE /api/v1/documents/{id}

Delete a document.

---

## Code Artifacts

### GET /api/v1/code-artifacts

List all code artifacts.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `project_id` | int | Filter by project |
| `language` | string | Filter by programming language |
| `tags` | string | Comma-separated tags |

**Response:**
```json
{
  "code_artifacts": [
    {
      "id": 1,
      "title": "Artifact Title",
      "description": "What this code does",
      "code": "def hello():\n    return 'Hello'",
      "language": "python",
      "tags": ["utility"],
      "created_at": "2024-12-05T10:00:00Z"
    }
  ],
  "total": 10
}
```

### GET /api/v1/code-artifacts/{id}

Get a single code artifact by ID.

### POST /api/v1/code-artifacts

Create a new code artifact.

**Request Body:**
```json
{
  "title": "Artifact Title",
  "description": "What this code does",
  "code": "def hello():\n    return 'Hello'",
  "language": "python",
  "tags": ["utility"]
}
```

### PUT /api/v1/code-artifacts/{id}

Update an existing code artifact.

### DELETE /api/v1/code-artifacts/{id}

Delete a code artifact.

---

## Graph

### GET /api/v1/graph

Get full knowledge graph for visualization. Returns all nodes and edges for the user.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_types` | string | `memory,entity,project,document,code_artifact` | Comma-separated list of node types to include |
| `project_id` | int | - | Filter to specific project |
| `include_entities` | bool | true | Include entity nodes (deprecated, use `node_types`) |
| `limit` | int | 100 | Max memories to include (max 500) |

**Node Types:**
- `memory` - Knowledge memories
- `entity` - People, organizations, devices
- `project` - Project contexts
- `document` - Long-form documents
- `code_artifact` - Code snippets

**Edge Types:**
- `memory_link` - Memory-to-memory connections
- `entity_memory` - Entity linked to memory
- `entity_relationship` - Entity-to-entity relationship
- `memory_project` - Memory linked to project
- `document_project` - Document belongs to project
- `code_artifact_project` - Code artifact belongs to project
- `memory_document` - Memory linked to document
- `memory_code_artifact` - Memory linked to code artifact

**Response:**
```json
{
  "nodes": [
    {
      "id": "memory_1",
      "type": "memory",
      "label": "Memory Title",
      "data": {
        "id": 1,
        "title": "Memory Title",
        "importance": 7,
        "tags": ["tag1"],
        "created_at": "2024-12-05T10:00:00Z"
      }
    },
    {
      "id": "entity_1",
      "type": "entity",
      "label": "Entity Name",
      "data": {
        "id": 1,
        "name": "Entity Name",
        "entity_type": "Individual"
      }
    },
    {
      "id": "project_1",
      "type": "project",
      "label": "Project Name",
      "data": {
        "id": 1,
        "name": "Project Name",
        "project_type": "development",
        "status": "active"
      }
    }
  ],
  "edges": [
    {
      "id": "memory_1_memory_2",
      "source": "memory_1",
      "target": "memory_2",
      "type": "memory_link"
    },
    {
      "id": "memory_1_project_1",
      "source": "memory_1",
      "target": "project_1",
      "type": "memory_project"
    }
  ],
  "meta": {
    "memory_count": 50,
    "entity_count": 10,
    "project_count": 3,
    "document_count": 5,
    "code_artifact_count": 8,
    "edge_count": 75,
    "memory_link_count": 25,
    "entity_relationship_count": 5,
    "entity_memory_count": 15,
    "memory_project_count": 12,
    "document_project_count": 5,
    "code_artifact_project_count": 8,
    "memory_document_count": 3,
    "memory_code_artifact_count": 2
  }
}
```

### GET /api/v1/graph/subgraph

Get subgraph centered on a specific node using efficient CTE traversal.
This is the recommended endpoint for graph visualization with depth-limited traversal.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | string | *required* | Center node (e.g., `memory_1`, `entity_5`, `project_3`, `document_2`, `code_artifact_4`) |
| `depth` | int | 2 | Traversal depth (1-3, clamped) |
| `node_types` | string | `memory,entity,project,document,code_artifact` | Comma-separated list of types to traverse |
| `max_nodes` | int | 200 | Maximum nodes to return (max 500) |

**Response:**
```json
{
  "nodes": [
    {
      "id": "memory_1",
      "type": "memory",
      "depth": 0,
      "label": "Center Memory",
      "data": {...}
    },
    {
      "id": "memory_2",
      "type": "memory",
      "depth": 1,
      "label": "Linked Memory",
      "data": {...}
    }
  ],
  "edges": [...],
  "meta": {
    "center_node_id": "memory_1",
    "depth": 2,
    "node_types": ["memory", "entity"],
    "max_nodes": 200,
    "memory_count": 5,
    "entity_count": 2,
    "project_count": 0,
    "document_count": 0,
    "code_artifact_count": 0,
    "edge_count": 6,
    "memory_link_count": 3,
    "entity_relationship_count": 1,
    "entity_memory_count": 2,
    "memory_project_count": 0,
    "document_project_count": 0,
    "code_artifact_project_count": 0,
    "memory_document_count": 0,
    "memory_code_artifact_count": 0,
    "truncated": false
  }
}
```

### GET /api/v1/graph/memory/{id}

**Deprecated:** Use `/api/v1/graph/subgraph?node_id=memory_{id}` instead.

Get subgraph centered on a specific memory.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `depth` | int | 1 | Link traversal depth (1-3) |

**Response:**
```json
{
  "nodes": [...],
  "edges": [...],
  "center_memory_id": 1,
  "meta": {
    "memory_count": 5,
    "edge_count": 4,
    "depth": 1
  }
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

For validation errors (400), the error may contain detailed field-level errors:

```json
{
  "error": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```
