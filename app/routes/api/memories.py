"""
REST API endpoints for Memory operations.

Phase 1 of the Web UI foundation (Issue #3).
Provides CRUD operations for memories with pagination, filtering, and semantic search.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.memory_models import (
    MemoryCreate,
    MemoryUpdate,
    MemoryQueryRequest,
    MemoryCreateResponse,
    MemoryListResponse,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register memory REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/memories", methods=["GET"])
    async def list_memories(request: Request) -> JSONResponse:
        """
        List memories with pagination, sorting, and filtering.

        Query params:
            limit: Max results per page (1-100, default 20)
            offset: Skip N results (default 0)
            sort_by: Sort field - created_at, updated_at (default created_at)
            sort_order: Sort direction - asc, desc (default desc)
            project_id: Filter by project (optional)
            importance_min: Minimum importance 1-10 (optional)
            tags: Comma-separated tags (optional)
            include_obsolete: Include obsolete memories (default false)
        """
        user = await get_user_from_request(request, mcp)

        # Parse query params with defaults
        params = request.query_params
        limit = min(int(params.get("limit", 20)), 100)
        offset = int(params.get("offset", 0))
        project_id = params.get("project_id")
        importance_min = params.get("importance_min")
        include_obsolete = params.get("include_obsolete", "false").lower() == "true"

        # Convert project_id to list if provided
        project_ids = [int(project_id)] if project_id else None

        # Get memories via service
        # Note: get_recent_memories returns sorted by created_at DESC by default
        # We request more than needed to account for filtering
        fetch_limit = limit + offset + 100  # Buffer for filtering
        memories = await mcp.memory_service.get_recent_memories(
            user_id=user.id,
            limit=fetch_limit,
            project_ids=project_ids
        )

        # Filter by importance if specified
        if importance_min:
            min_importance = int(importance_min)
            memories = [m for m in memories if m.importance >= min_importance]

        # Filter obsolete if needed
        if not include_obsolete:
            memories = [m for m in memories if not m.is_obsolete]

        # Get total before pagination
        total = len(memories)

        # Apply pagination
        memories = memories[offset:offset + limit]

        response = MemoryListResponse(
            memories=memories,
            total=total,
            limit=limit,
            offset=offset
        )

        return JSONResponse(response.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/memories/{memory_id}", methods=["GET"])
    async def get_memory(request: Request) -> JSONResponse:
        """Get a single memory by ID."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        try:
            memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=memory_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

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
        except Exception as e:
            return JSONResponse({"error": f"Invalid request body: {str(e)}"}, status_code=400)

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
        except Exception as e:
            return JSONResponse({"error": f"Invalid request body: {str(e)}"}, status_code=400)

        try:
            memory = await mcp.memory_service.update_memory(
                user_id=user.id,
                memory_id=memory_id,
                updated_memory=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

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
        except Exception as e:
            return JSONResponse({"error": f"Invalid request body: {str(e)}"}, status_code=400)

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

        try:
            linked_ids = await mcp.memory_service.link_memories(
                user_id=user.id,
                memory_id=memory_id,
                related_ids=related_ids
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        return JSONResponse({"linked_ids": linked_ids})

    @mcp.custom_route("/api/v1/memories/{memory_id}/links", methods=["GET"])
    async def get_memory_links(request: Request) -> JSONResponse:
        """Get memories linked to this memory."""
        user = await get_user_from_request(request, mcp)
        memory_id = int(request.path_params["memory_id"])

        params = request.query_params
        limit = min(int(params.get("limit", 20)), 100)

        # Get the memory first to access linked_memory_ids
        try:
            memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=memory_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        if not memory:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        # Fetch linked memories
        linked_memories = []
        for linked_id in memory.linked_memory_ids[:limit]:
            try:
                linked_memory = await mcp.memory_service.get_memory(
                    user_id=user.id,
                    memory_id=linked_id
                )
                if linked_memory:
                    linked_memories.append(linked_memory)
            except NotFoundError:
                # Skip if linked memory no longer exists
                continue

        return JSONResponse({
            "memory_id": memory_id,
            "linked_memories": [m.model_dump(mode="json") for m in linked_memories]
        })

    @mcp.custom_route("/api/v1/memories/{memory_id}/links/{target_id}", methods=["DELETE"])
    async def delete_memory_link(request: Request) -> JSONResponse:
        """Remove a specific link between memories."""
        # TODO: Need to add unlink_memories method to service/repository
        # For now, return not implemented
        return JSONResponse(
            {"error": "Delete link not yet implemented"},
            status_code=501
        )
