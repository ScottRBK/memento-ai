# REST API Routes Implementation

## Overview

This document outlines the implementation of REST API endpoints for Forgetful, serving as the foundation for a future Web UI with graph visualization and search capabilities (GitHub Issue #3).

## Implementation Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Memory Endpoints | ✅ Complete | 9 endpoints, 32 tests passing |
| Phase 2: Entity Endpoints | 🔲 Planned | - |
| Phase 3: Other Resources | 🔲 Planned | Projects, Documents, Code Artifacts |
| Phase 4: Graph Endpoints | 🔲 Planned | For visualization UI |
| Phase 5: Authentication | ✅ Complete | HTTP Bearer token support via FastMCP auth providers |

### Files Created/Modified (Phase 1)

| File | Status | Description |
|------|--------|-------------|
| `app/middleware/auth.py` | ✅ Modified | Added `get_user_from_request()` |
| `app/models/memory_models.py` | ✅ Modified | Added `MemoryListResponse` |
| `app/routes/api/memories.py` | ✅ Created | All 9 endpoints |
| `main.py` | ✅ Modified | Registered memories routes |
| `tests/e2e_sqlite/conftest.py` | ✅ Modified | Added `http_client` fixture |
| `tests/e2e_sqlite/test_api_memories.py` | ✅ Created | 32 E2E tests |

## Design Decisions

Based on community feedback from @riffi:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Versioning | `/api/v1/...` | Future compatibility |
| Pagination | Offset-based (`limit`, `offset`) | Simple, familiar pattern |
| Sorting | `sort_by` + `sort_order` | Consistent pagination ordering |
| Filters | All optional | Flexibility; pagination prevents memory dumps |
| Obsolete handling | `include_obsolete=false` default | Clean results by default |
| Link behavior | POST appends, DELETE removes | Non-destructive by default |
| Auth (MVP) | Default user (no auth) | Fast iteration; auth as follow-up |

---

## Phase 1: Memory Endpoints

### Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| `GET` | `/api/v1/memories` | List memories (paginated) | ✅ |
| `GET` | `/api/v1/memories/{id}` | Get single memory | ✅ |
| `POST` | `/api/v1/memories` | Create memory | ✅ |
| `PUT` | `/api/v1/memories/{id}` | Update memory | ✅ |
| `DELETE` | `/api/v1/memories/{id}` | Mark obsolete (soft delete) | ✅ |
| `POST` | `/api/v1/memories/search` | Semantic search | ✅ |
| `POST` | `/api/v1/memories/{id}/links` | Link memories | ✅ |
| `GET` | `/api/v1/memories/{id}/links` | Get linked memories | ✅ |
| `DELETE` | `/api/v1/memories/{id}/links/{target_id}` | Remove specific link | ⚠️ 501 |

> **Note:** Delete link endpoint returns 501 Not Implemented - requires `unlink_memories` method in service/repository.

### Query Parameters for GET /api/v1/memories

| Param | Type | Default | Description | Status |
|-------|------|---------|-------------|--------|
| `limit` | int | 20 | Max results per page (1-100) | ✅ |
| `offset` | int | 0 | Skip N results | ✅ |
| `sort_by` | string | `created_at` | Sort field: `created_at`, `updated_at`, `importance` | ✅ |
| `sort_order` | string | `desc` | Sort direction: `asc`, `desc` | ✅ |
| `project_id` | int | null | Filter by project (optional) | ✅ |
| `importance_min` | int | null | Minimum importance 1-10 (optional) | ✅ |
| `tags` | string | null | Comma-separated tags, OR logic (optional) | ✅ |
| `include_obsolete` | bool | false | Include soft-deleted memories | ✅ |

> **Validation Notes:**
> - Invalid params (non-integer limit/offset, invalid sort_by/sort_order) return 400 error
> - `limit` must be 1-100, `offset` must be non-negative
> - `tags` uses OR logic (returns memories matching ANY specified tag)

### Request/Response Bodies

#### POST /api/v1/memories (Create)
```json
// Request: MemoryCreate
{
  "title": "string (max 200 chars)",
  "content": "string (max 2000 chars)",
  "context": "string (max 500 chars)",
  "keywords": ["string"],
  "tags": ["string"],
  "importance": 7,
  "project_ids": [1, 2],
  "code_artifact_ids": [],
  "document_ids": []
}

// Response: MemoryCreateResponse
{
  "id": 123,
  "title": "...",
  "linked_memory_ids": [45, 67],
  "project_ids": [1, 2],
  "code_artifact_ids": [],
  "document_ids": [],
  "similar_memories": [
    {"id": 45, "title": "...", "keywords": [...], "tags": [...], "importance": 8, "created_at": "...", "updated_at": "..."}
  ]
}
```

#### PUT /api/v1/memories/{id} (Update)
```json
// Request: MemoryUpdate (all fields optional)
{
  "title": "string",
  "content": "string",
  "context": "string",
  "keywords": ["string"],
  "tags": ["string"],
  "importance": 8,
  "project_ids": [1, 2, 3]
}

// Response: Memory
{
  "id": 123,
  "title": "...",
  "content": "...",
  "context": "...",
  "keywords": [...],
  "tags": [...],
  "importance": 8,
  "project_ids": [1, 2, 3],
  "linked_memory_ids": [...],
  "code_artifact_ids": [...],
  "document_ids": [...],
  "is_obsolete": false,
  "obsolete_reason": null,
  "superseded_by": null,
  "obsoleted_at": null,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-02T00:00:00Z"
}
```

#### DELETE /api/v1/memories/{id} (Mark Obsolete)
```json
// Request
{
  "reason": "Superseded by updated architecture",
  "superseded_by": 456  // optional
}

// Response
{
  "success": true
}
```

#### POST /api/v1/memories/search (Semantic Search)
```json
// Request: MemoryQueryRequest
{
  "query": "Python logging best practices",
  "query_context": "Looking for patterns to implement in my service",
  "k": 5,
  "include_links": 1,
  "token_context_threshold": 8000,
  "max_links_per_primary": 5,
  "importance_threshold": 6,
  "project_ids": [4],
  "strict_project_filter": false
}

// Response: MemoryQueryResult
{
  "query": "Python logging best practices",
  "primary_memories": [...],
  "linked_memories": [...],
  "total_count": 8,
  "token_count": 3500,
  "truncated": false
}
```

#### POST /api/v1/memories/{id}/links (Link Memories)
```json
// Request
{
  "related_ids": [45, 67, 89]
}

// Response
{
  "linked_ids": [45, 67, 89]
}
```

#### GET /api/v1/memories (List Response)
```json
{
  "memories": [...],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

---

## Implementation Details

### File Structure

```
app/
├── routes/
│   └── api/
│       ├── __init__.py
│       ├── health.py          # Existing
│       └── memories.py        # NEW
├── models/
│   └── memory_models.py       # Add MemoryListResponse
├── middleware/
│   └── auth.py                # Add get_user_from_request
└── ...

tests/
└── e2e_sqlite/
    └── test_api_memories.py   # NEW
```

### 1. Auth Helper (app/middleware/auth.py)

The `get_user_from_request` function handles HTTP authentication:

```python
from starlette.requests import Request
from fastmcp import FastMCP

async def get_user_from_request(request: Request, mcp: FastMCP) -> User:
    """
    Get user for HTTP routes (non-MCP endpoints).

    Uses the same auth provider as MCP routes via mcp.auth.verify_token(),
    supporting all FastMCP auth providers (JWT, OAuth2, GitHub, Google, Azure, etc.).

    Raises:
        ValueError: If auth is enabled but token is missing, invalid, or lacks required claims
    """
    user_service: UserService = mcp.user_service

    # Check if auth is configured via mcp.auth
    if not mcp.auth:
        # No auth configured - use default user
        default_user = UserCreate(...)
        return await user_service.get_or_create_user(user=default_user)

    # Auth enabled - extract Bearer token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header")

    token = auth_header[7:]  # Strip "Bearer " prefix

    # Validate token using configured auth provider (works with ANY provider)
    access_token = await mcp.auth.verify_token(token)
    if access_token is None:
        raise ValueError("Invalid or expired token")

    # Extract claims and provision user (same pattern as MCP auth)
    claims = access_token.claims
    sub = claims.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub' claim")

    name = claims.get("name") or claims.get("preferred_username") or claims.get("login") or f"User {sub}"
    email = claims.get("email") or f"{sub}@oauth.local"

    user_data = UserCreate(external_id=sub, name=name, email=email)
    return await user_service.get_or_create_user(user=user_data)
```

Route handlers catch `ValueError` and return 401:

```python
@mcp.custom_route("/api/v1/memories", methods=["GET"])
async def list_memories(request: Request) -> JSONResponse:
    try:
        user = await get_user_from_request(request, mcp)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=401)
    # ... rest of handler
```

### 2. Response Model (app/models/memory_models.py)

Add pagination wrapper:

```python
class MemoryListResponse(BaseModel):
    """Paginated list of memories"""
    memories: List[Memory]
    total: int
    limit: int
    offset: int
```

### 3. Routes (app/routes/api/memories.py)

```python
"""
REST API endpoints for Memory operations.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoryQueryRequest,
    MemoryCreateResponse,
    MemoryListResponse,
)
from app.middleware.auth import get_user_from_request

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register memory REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/memories", methods=["GET"])
    async def list_memories(request: Request) -> JSONResponse:
        """List memories with pagination, sorting, and filtering."""
        user = await get_user_from_request(request, mcp)

        # Parse query params
        params = request.query_params
        limit = min(int(params.get("limit", 20)), 100)
        offset = int(params.get("offset", 0))
        sort_by = params.get("sort_by", "created_at")
        sort_order = params.get("sort_order", "desc")
        project_id = params.get("project_id")
        importance_min = params.get("importance_min")
        tags = params.get("tags")
        include_obsolete = params.get("include_obsolete", "false").lower() == "true"

        # Convert project_id to list if provided
        project_ids = [int(project_id)] if project_id else None

        # Get memories via service
        # NOTE: May need to extend service to support sorting and total count
        memories = await mcp.memory_service.get_recent_memories(
            user_id=user.id,
            limit=limit,
            project_ids=project_ids
        )

        # Filter by importance if specified
        if importance_min:
            memories = [m for m in memories if m.importance >= int(importance_min)]

        # Filter obsolete if needed
        if not include_obsolete:
            memories = [m for m in memories if not m.is_obsolete]

        response = MemoryListResponse(
            memories=memories,
            total=len(memories),  # TODO: Get actual total from repo
            limit=limit,
            offset=offset
        )

        return JSONResponse(response.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/memories/{memory_id}", methods=["GET"])
    async def get_memory(request: Request) -> JSONResponse:
        """Get a single memory by ID."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        memory = await mcp.memory_service.get_memory(
            user_id=user.id,
            memory_id=memory_id
        )

        if not memory:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        return JSONResponse(memory.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/memories", methods=["POST"])
    async def create_memory(request: Request) -> JSONResponse:
        """Create a new memory."""
        user = await get_user_from_request(request, mcp)

        try:
            body = await request.json()
            memory_data = MemoryCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        memory, similar_memories = await mcp.memory_service.create_memory(
            user_id=user.id,
            memory_data=memory_data
        )

        response = MemoryCreateResponse(
            id=memory.id,
            title=memory.title,
            linked_memory_ids=memory.linked_memory_ids,
            project_ids=memory.project_ids,
            code_artifact_ids=memory.code_artifact_ids,
            document_ids=memory.document_ids,
            similar_memories=similar_memories
        )

        return JSONResponse(response.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/memories/{memory_id}", methods=["PUT"])
    async def update_memory(request: Request) -> JSONResponse:
        """Update an existing memory."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        try:
            body = await request.json()
            update_data = MemoryUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        memory = await mcp.memory_service.update_memory(
            user_id=user.id,
            memory_id=memory_id,
            updated_memory=update_data
        )

        if not memory:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        return JSONResponse(memory.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/memories/{memory_id}", methods=["DELETE"])
    async def delete_memory(request: Request) -> JSONResponse:
        """Mark a memory as obsolete (soft delete)."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        try:
            body = await request.json()
            reason = body.get("reason", "Marked obsolete via API")
            superseded_by = body.get("superseded_by")
        except Exception:
            reason = "Marked obsolete via API"
            superseded_by = None

        success = await mcp.memory_service.mark_memory_obsolete(
            user_id=user.id,
            memory_id=memory_id,
            reason=reason,
            superseded_by=superseded_by
        )

        if not success:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        return JSONResponse({"success": True})

    @mcp.custom_route("/api/v1/memories/search", methods=["POST"])
    async def search_memories(request: Request) -> JSONResponse:
        """Semantic search across memories."""
        user = await get_user_from_request(request, mcp)

        try:
            body = await request.json()
            query_request = MemoryQueryRequest(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        result = await mcp.memory_service.query_memory(
            user_id=user.id,
            memory_query=query_request
        )

        return JSONResponse(result.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/memories/{memory_id}/links", methods=["POST"])
    async def link_memories(request: Request) -> JSONResponse:
        """Link memories together (appends to existing links)."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        try:
            body = await request.json()
            related_ids = body.get("related_ids", [])
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        if not related_ids:
            return JSONResponse({"error": "related_ids is required"}, status_code=400)

        linked_ids = await mcp.memory_service.link_memories(
            user_id=user.id,
            memory_id=memory_id,
            related_ids=related_ids
        )

        return JSONResponse({"linked_ids": linked_ids})

    @mcp.custom_route("/api/v1/memories/{memory_id}/links", methods=["GET"])
    async def get_memory_links(request: Request) -> JSONResponse:
        """Get memories linked to this memory."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        params = request.query_params
        limit = min(int(params.get("limit", 20)), 100)

        # Get the memory first to access linked_memory_ids
        memory = await mcp.memory_service.get_memory(
            user_id=user.id,
            memory_id=memory_id
        )

        if not memory:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        # Fetch linked memories
        linked_memories = []
        for linked_id in memory.linked_memory_ids[:limit]:
            linked_memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=linked_id
            )
            if linked_memory:
                linked_memories.append(linked_memory)

        return JSONResponse({
            "memory_id": memory_id,
            "linked_memories": [m.model_dump(mode="json") for m in linked_memories]
        })

    @mcp.custom_route("/api/v1/memories/{memory_id}/links/{target_id}", methods=["DELETE"])
    async def delete_memory_link(request: Request) -> JSONResponse:
        """Remove a specific link between memories."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])
        target_id = int(request.path_params["target_id"])

        # TODO: Need to add unlink_memories method to service/repository
        # For now, return not implemented
        return JSONResponse(
            {"error": "Delete link not yet implemented"},
            status_code=501
        )
```

### 4. Registration (main.py)

Add import and registration:

```python
from app.routes.api import health, memories

# In the route registration section:
health.register(mcp)
memories.register(mcp)
```

---

## E2E Tests (tests/e2e_sqlite/test_api_memories.py)

```python
"""
E2E tests for Memory REST API endpoints.
Uses in-memory SQLite for test isolation.
"""
import pytest
from httpx import AsyncClient, ASGITransport

# Test fixtures and setup...

class TestMemoryAPI:
    """Test Memory CRUD endpoints."""

    async def test_list_memories_empty(self, client: AsyncClient):
        """GET /api/v1/memories returns empty list initially."""
        response = await client.get("/api/v1/memories")
        assert response.status_code == 200
        data = response.json()
        assert data["memories"] == []
        assert data["total"] == 0

    async def test_create_memory(self, client: AsyncClient):
        """POST /api/v1/memories creates a new memory."""
        payload = {
            "title": "Test Memory",
            "content": "This is test content for the memory.",
            "context": "Testing the API",
            "keywords": ["test", "api"],
            "tags": ["test"],
            "importance": 7
        }
        response = await client.post("/api/v1/memories", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["title"] == "Test Memory"

    async def test_get_memory(self, client: AsyncClient, created_memory_id: int):
        """GET /api/v1/memories/{id} returns the memory."""
        response = await client.get(f"/api/v1/memories/{created_memory_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_memory_id

    async def test_get_memory_not_found(self, client: AsyncClient):
        """GET /api/v1/memories/{id} returns 404 for missing memory."""
        response = await client.get("/api/v1/memories/99999")
        assert response.status_code == 404

    async def test_update_memory(self, client: AsyncClient, created_memory_id: int):
        """PUT /api/v1/memories/{id} updates the memory."""
        payload = {"title": "Updated Title", "importance": 9}
        response = await client.put(
            f"/api/v1/memories/{created_memory_id}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["importance"] == 9

    async def test_delete_memory(self, client: AsyncClient, created_memory_id: int):
        """DELETE /api/v1/memories/{id} marks memory as obsolete."""
        payload = {"reason": "Test deletion"}
        response = await client.delete(
            f"/api/v1/memories/{created_memory_id}",
            json=payload
        )
        assert response.status_code == 200
        assert response.json()["success"] == True

    async def test_search_memories(self, client: AsyncClient, created_memory_id: int):
        """POST /api/v1/memories/search performs semantic search."""
        payload = {
            "query": "test content",
            "query_context": "Looking for test memories",
            "k": 5
        }
        response = await client.post("/api/v1/memories/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "primary_memories" in data
        assert "token_count" in data

    async def test_link_memories(self, client: AsyncClient):
        """POST /api/v1/memories/{id}/links creates links."""
        # Create two memories first
        m1 = await client.post("/api/v1/memories", json={
            "title": "Memory 1",
            "content": "First memory",
            "context": "Testing links",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 7
        })
        m2 = await client.post("/api/v1/memories", json={
            "title": "Memory 2",
            "content": "Second memory",
            "context": "Testing links",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 7
        })

        m1_id = m1.json()["id"]
        m2_id = m2.json()["id"]

        # Link them
        response = await client.post(
            f"/api/v1/memories/{m1_id}/links",
            json={"related_ids": [m2_id]}
        )
        assert response.status_code == 200
        assert m2_id in response.json()["linked_ids"]

    async def test_list_with_pagination(self, client: AsyncClient):
        """GET /api/v1/memories respects limit and offset."""
        # Create 5 memories
        for i in range(5):
            await client.post("/api/v1/memories", json={
                "title": f"Memory {i}",
                "content": f"Content {i}",
                "context": "Pagination test",
                "keywords": ["test"],
                "tags": ["test"],
                "importance": 7
            })

        # Get first page
        response = await client.get("/api/v1/memories?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["memories"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    async def test_list_with_filters(self, client: AsyncClient):
        """GET /api/v1/memories filters by importance."""
        # Create memories with different importance
        await client.post("/api/v1/memories", json={
            "title": "Low importance",
            "content": "Low",
            "context": "Filter test",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 3
        })
        await client.post("/api/v1/memories", json={
            "title": "High importance",
            "content": "High",
            "context": "Filter test",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 9
        })

        # Filter by importance
        response = await client.get("/api/v1/memories?importance_min=8")
        assert response.status_code == 200
        data = response.json()
        for memory in data["memories"]:
            assert memory["importance"] >= 8
```

---

## Implementation Order

1. ✅ **Add auth helper** (`app/middleware/auth.py`)
   - Added `get_user_from_request()` function

2. ✅ **Add response model** (`app/models/memory_models.py`)
   - Added `MemoryListResponse` class

3. ✅ **Create routes** (`app/routes/api/memories.py`)
   - Implemented all 9 endpoints with `NotFoundError` handling

4. ✅ **Register routes** (`main.py`)
   - Imported and registered memories routes

5. ✅ **Add E2E tests** (`tests/e2e_sqlite/test_api_memories.py`)
   - 32 comprehensive tests covering all endpoints and edge cases
   - Added `http_client` fixture to `conftest.py`
   - Includes validation, sorting, tag filtering, pagination, and include_obsolete tests

6. ✅ **Run tests**
   ```bash
   uv run pytest tests/e2e_sqlite/test_api_memories.py -v
   # Result: 32 passed
   ```

---

## Future Phases

### Phase 2: Entity Endpoints
- `/api/v1/entities` CRUD
- Entity-memory links
- Entity relationships

### Phase 3: Other Resources
- `/api/v1/projects`
- `/api/v1/documents`
- `/api/v1/code-artifacts`

### Phase 4: Graph Endpoints
- `/api/v1/graph` (nodes + edges)
- Power visualization UI

### Phase 5: Authentication ✅
- Implemented `get_user_from_request` with `mcp.auth.verify_token()`
- Supports all FastMCP auth providers (JWT, OAuth2, GitHub, Google, Azure, etc.)
- Returns 401 Unauthorized for missing/invalid tokens
- E2E tests with `StaticTokenVerifier`

---

## Notes

- All endpoints use the existing service layer - no new business logic
- MVP uses default user (no auth) for fast iteration
- Follows existing `health.py` pattern for route registration
- Tests use in-memory SQLite for isolation and speed

## Implementation Learnings (Phase 1)

1. **Exception Handling**: Routes catch `NotFoundError` from repository layer and return proper 404 responses
2. **HTTP Testing**: Created `http_client` fixture using `httpx.AsyncClient` with `ASGITransport` for testing custom routes
3. **Auto-linking**: When testing link creation, auto-linking may have already created the link during memory creation
4. **FastMCP HTTP App**: Use `mcp.http_app()` (not deprecated `sse_app()`) for ASGI transport
5. **Strict Validation**: Query params validated with 400 errors for invalid values (not silent defaults)
6. **Repository Layer**: Full pagination, sorting, tag filtering, and include_obsolete implemented at repository level
7. **Dual Database**: Both SQLite and Postgres repositories updated with same interface (tuple return with total count)
