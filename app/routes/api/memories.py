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
from typing import Any

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

# Valid values for query parameters
VALID_SORT_BY = {"created_at", "updated_at", "importance"}
VALID_SORT_ORDER = {"asc", "desc"}


def parse_int_param(params: Any, name: str, default: int | None = None) -> int | None:
    """
    Parse integer query parameter with strict validation.

    Args:
        params: Query params object
        name: Parameter name
        default: Default value if param not provided

    Returns:
        Parsed integer or default

    Raises:
        ValueError: If value is not a valid integer
    """
    raw = params.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid value for '{name}': must be an integer")


def register(mcp: FastMCP):
    """Register memory REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/memories", methods=["GET"])
    async def list_memories(request: Request) -> JSONResponse:
        """
        List memories with pagination, sorting, and filtering.

        Query params:
            limit: Max results per page (1-100, default 20)
            offset: Skip N results (default 0)
            sort_by: Sort field - created_at, updated_at, importance (default created_at)
            sort_order: Sort direction - asc, desc (default desc)
            project_id: Filter by project (optional)
            importance_min: Minimum importance 1-10 (optional)
            tags: Comma-separated tags (optional)
            include_obsolete: Include obsolete memories (default false)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params

        # Parse and validate query params with strict validation
        try:
            limit = parse_int_param(params, "limit", 20)
            offset = parse_int_param(params, "offset", 0)
            importance_min = parse_int_param(params, "importance_min")
            project_id = parse_int_param(params, "project_id")
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        # Validate limit range
        if limit < 1 or limit > 100:
            return JSONResponse(
                {"error": "limit must be between 1 and 100"},
                status_code=400
            )

        # Validate offset is non-negative
        if offset < 0:
            return JSONResponse(
                {"error": "offset must be non-negative"},
                status_code=400
            )

        # Validate sort_by
        sort_by = params.get("sort_by", "created_at")
        if sort_by not in VALID_SORT_BY:
            return JSONResponse(
                {"error": f"sort_by must be one of: {', '.join(VALID_SORT_BY)}"},
                status_code=400
            )

        # Validate sort_order
        sort_order = params.get("sort_order", "desc")
        if sort_order not in VALID_SORT_ORDER:
            return JSONResponse(
                {"error": f"sort_order must be one of: {', '.join(VALID_SORT_ORDER)}"},
                status_code=400
            )

        # Parse tags (comma-separated)
        tags_raw = params.get("tags")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else None

        # Parse include_obsolete
        include_obsolete = params.get("include_obsolete", "false").lower() == "true"

        # Convert project_id to list if provided
        project_ids = [project_id] if project_id else None

        # Get memories via service (now returns tuple with total count)
        memories, total = await mcp.memory_service.get_recent_memories(
            user_id=user.id,
            limit=limit,
            offset=offset,
            project_ids=project_ids,
            include_obsolete=include_obsolete,
            sort_by=sort_by,
            sort_order=sort_order,
            tags=tags,
        )

        # Filter by importance if specified (post-query filter)
        if importance_min:
            memories = [m for m in memories if m.importance >= importance_min]
            # Note: total count may not reflect this filter accurately
            # Consider adding importance_min to repository layer in future

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

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
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        memory_id = int(request.path_params["memory_id"])
        target_id = int(request.path_params["target_id"])

        try:
            success = await mcp.memory_service.unlink_memories(
                user_id=user.id,
                memory_id=memory_id,
                target_id=target_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        if not success:
            return JSONResponse({"error": "Link not found"}, status_code=404)

        return JSONResponse({"success": True})
