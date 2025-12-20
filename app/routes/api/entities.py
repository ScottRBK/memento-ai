"""
REST API endpoints for Entity operations.

Phase 2 of the Web UI foundation (Issue #3).
Provides CRUD operations for entities with relationships and memory links.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from typing import Any

from app.models.entity_models import (
    EntityCreate,
    EntityUpdate,
    EntityRelationshipCreate,
    EntityRelationshipUpdate,
    EntityType,
    EntityListResponse,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def parse_int_param(params: Any, name: str, default: int | None = None) -> int | None:
    """Parse integer query parameter with strict validation.

    Args:
        params: Query parameters object
        name: Parameter name to extract
        default: Default value if parameter not provided

    Returns:
        Parsed integer value or default

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
    """Register entity REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/entities", methods=["GET"])
    async def list_entities(request: Request) -> JSONResponse:
        """
        List entities with optional filtering and pagination.

        Query params:
            entity_type: Filter by type (individual, organization, team, device, other)
            limit: Maximum results per page (1-100, default 20)
            offset: Number of results to skip (default 0)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params

        # Parse and validate pagination parameters
        try:
            limit = parse_int_param(params, "limit", 20)
            offset = parse_int_param(params, "offset", 0)
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

        entity_type_str = params.get("entity_type")

        # Convert string to EntityType enum if provided
        entity_type = None
        if entity_type_str:
            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid entity_type: {entity_type_str}. Valid values: Individual, Organization, Team, Device, Other"},
                    status_code=400
                )

        entities, total = await mcp.entity_service.list_entities(
            user_id=user.id,
            entity_type=entity_type,
            limit=limit,
            offset=offset
        )

        response = EntityListResponse(
            entities=entities,
            total=total,
            limit=limit,
            offset=offset
        )

        return JSONResponse(response.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/entities/{entity_id}", methods=["GET"])
    async def get_entity(request: Request) -> JSONResponse:
        """Get a single entity by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        try:
            entity = await mcp.entity_service.get_entity(
                user_id=user.id,
                entity_id=entity_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Entity not found"}, status_code=404)

        return JSONResponse(entity.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/entities", methods=["POST"])
    async def create_entity(request: Request) -> JSONResponse:
        """Create a new entity."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            entity_data = EntityCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        entity = await mcp.entity_service.create_entity(
            user_id=user.id,
            entity_data=entity_data
        )

        return JSONResponse(entity.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/entities/{entity_id}", methods=["PUT"])
    async def update_entity(request: Request) -> JSONResponse:
        """Update an existing entity."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        try:
            body = await request.json()
            update_data = EntityUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            entity = await mcp.entity_service.update_entity(
                user_id=user.id,
                entity_id=entity_id,
                entity_data=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Entity not found"}, status_code=404)

        return JSONResponse(entity.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/entities/{entity_id}", methods=["DELETE"])
    async def delete_entity(request: Request) -> JSONResponse:
        """Delete an entity."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        success = await mcp.entity_service.delete_entity(
            user_id=user.id,
            entity_id=entity_id
        )

        if not success:
            return JSONResponse({"error": "Entity not found"}, status_code=404)

        return JSONResponse({"success": True})

    @mcp.custom_route("/api/v1/entities/search", methods=["POST"])
    async def search_entities(request: Request) -> JSONResponse:
        """Search entities by name or description."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            query = body.get("query", "")
            entity_type_str = body.get("entity_type")
            limit = min(int(body.get("limit", 10)), 100)
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        if not query:
            return JSONResponse({"error": "query is required"}, status_code=400)

        # Convert string to EntityType enum if provided
        entity_type = None
        if entity_type_str:
            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid entity_type: {entity_type_str}. Valid values: Individual, Organization, Team, Device, Other"},
                    status_code=400
                )

        entities = await mcp.entity_service.search_entities(
            user_id=user.id,
            search_query=query,
            entity_type=entity_type,
            limit=limit
        )

        return JSONResponse({
            "entities": [e.model_dump(mode="json") for e in entities],
            "total": len(entities)
        })

    # Entity-Memory Links
    @mcp.custom_route("/api/v1/entities/{entity_id}/memories", methods=["POST"])
    async def link_entity_to_memory(request: Request) -> JSONResponse:
        """Link an entity to a memory."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        try:
            body = await request.json()
            memory_id = body.get("memory_id")
        except Exception:
            return JSONResponse({"error": "Invalid request body"}, status_code=400)

        if not memory_id:
            return JSONResponse({"error": "memory_id is required"}, status_code=400)

        try:
            success = await mcp.entity_service.link_entity_to_memory(
                user_id=user.id,
                entity_id=entity_id,
                memory_id=memory_id
            )
        except NotFoundError as e:
            return JSONResponse({"error": str(e)}, status_code=404)

        return JSONResponse({"success": success})

    @mcp.custom_route("/api/v1/entities/{entity_id}/memories/{memory_id}", methods=["DELETE"])
    async def unlink_entity_from_memory(request: Request) -> JSONResponse:
        """Remove link between entity and memory."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])
        memory_id = int(request.path_params["memory_id"])

        try:
            success = await mcp.entity_service.unlink_entity_from_memory(
                user_id=user.id,
                entity_id=entity_id,
                memory_id=memory_id
            )
        except NotFoundError as e:
            return JSONResponse({"error": str(e)}, status_code=404)

        if not success:
            return JSONResponse({"error": "Link not found"}, status_code=404)

        return JSONResponse({"success": True})

    @mcp.custom_route("/api/v1/entities/{entity_id}/memories", methods=["GET"])
    async def get_entity_memories(request: Request) -> JSONResponse:
        """Get all memories linked to an entity."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        try:
            memory_ids, count = await mcp.entity_service.get_entity_memories(
                user_id=user.id,
                entity_id=entity_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Entity not found"}, status_code=404)

        return JSONResponse({
            "memory_ids": memory_ids,
            "count": count
        })

    # Entity Relationships
    @mcp.custom_route("/api/v1/entities/{entity_id}/relationships", methods=["GET"])
    async def get_entity_relationships(request: Request) -> JSONResponse:
        """Get relationships for an entity."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_id = int(request.path_params["entity_id"])

        try:
            relationships = await mcp.entity_service.get_entity_relationships(
                user_id=user.id,
                entity_id=entity_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Entity not found"}, status_code=404)

        return JSONResponse({
            "relationships": [r.model_dump(mode="json") for r in relationships],
            "total": len(relationships)
        })

    @mcp.custom_route("/api/v1/entities/{entity_id}/relationships", methods=["POST"])
    async def create_entity_relationship(request: Request) -> JSONResponse:
        """Create a relationship between entities."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        source_entity_id = int(request.path_params["entity_id"])

        try:
            body = await request.json()
            # Add source_entity_id to body for validation
            body["source_entity_id"] = source_entity_id
            relationship_data = EntityRelationshipCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            relationship = await mcp.entity_service.create_entity_relationship(
                user_id=user.id,
                relationship_data=relationship_data
            )
        except NotFoundError as e:
            return JSONResponse({"error": str(e)}, status_code=404)

        return JSONResponse(relationship.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/entities/relationships/{relationship_id}", methods=["PUT"])
    async def update_entity_relationship(request: Request) -> JSONResponse:
        """Update an entity relationship."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        relationship_id = int(request.path_params["relationship_id"])

        try:
            body = await request.json()
            update_data = EntityRelationshipUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            relationship = await mcp.entity_service.update_entity_relationship(
                user_id=user.id,
                relationship_id=relationship_id,
                relationship_data=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Relationship not found"}, status_code=404)

        return JSONResponse(relationship.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/entities/relationships/{relationship_id}", methods=["DELETE"])
    async def delete_entity_relationship(request: Request) -> JSONResponse:
        """Delete an entity relationship."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        relationship_id = int(request.path_params["relationship_id"])

        success = await mcp.entity_service.delete_entity_relationship(
            user_id=user.id,
            relationship_id=relationship_id
        )

        if not success:
            return JSONResponse({"error": "Relationship not found"}, status_code=404)

        return JSONResponse({"success": True})
