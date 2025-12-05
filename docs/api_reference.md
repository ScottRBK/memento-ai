# REST API Reference

Forgetful exposes a REST API for web UI integration and external access. All endpoints require authentication via HTTP Bearer token.

**Base URL:** `http://localhost:8020/api/v1`

## Authentication

All API requests require a Bearer token in the Authorization header:

```
Authorization: Bearer <your-api-key>
```

Configure the API key via environment variable `API_KEY` or in your config file.

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
      "project_ids": [1]
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
  "project_id": 1
}
```

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
  "tags": ["updated-tag"]
}
```

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

Get graph data for visualization (nodes and edges).

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_id` | int | - | Filter to specific project |
| `include_entities` | bool | true | Include entity nodes |
| `limit` | int | 100 | Max memories to include (max 500) |

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
    }
  ],
  "edges": [
    {
      "id": "memory_1_memory_2",
      "source": "memory_1",
      "target": "memory_2",
      "type": "memory_link"
    }
  ],
  "meta": {
    "memory_count": 50,
    "entity_count": 10,
    "edge_count": 25
  }
}
```

### GET /api/v1/graph/memory/{id}

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
