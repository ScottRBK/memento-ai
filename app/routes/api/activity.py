"""
REST API endpoints for Activity operations.

Provides read access to the activity log for event-driven architecture (Issue #7).
"""

from datetime import datetime
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
import logging

from app.middleware.auth import get_user_from_request
from app.models.activity_models import EntityType, ActionType, ActorType

logger = logging.getLogger(__name__)


def parse_int_param(params, key: str, default: int) -> int:
    """Parse integer query parameter with default."""
    value = params.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_datetime_param(params, key: str) -> datetime | None:
    """Parse ISO 8601 datetime query parameter."""
    value = params.get(key)
    if value is None:
        return None
    try:
        # Handle both with and without timezone
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def register(mcp: FastMCP):
    """Register activity REST routes with FastMCP."""

    @mcp.custom_route("/api/v1/activity", methods=["GET"])
    async def list_activity(request: Request) -> JSONResponse:
        """
        List activity events with filtering and pagination.

        Query params:
            entity_type: Filter by entity type (memory, project, document, etc.)
            action: Filter by action (created, updated, deleted, read, queried)
            entity_id: Filter by specific entity ID
            actor: Filter by actor (user, system, llm-maintenance)
            since: Only events after this timestamp (ISO 8601)
            until: Only events before this timestamp (ISO 8601)
            limit: Maximum results (1-100, default 50)
            offset: Skip N results for pagination (default 0)

        Returns:
            {
                "events": [...],
                "total": int,
                "limit": int,
                "offset": int
            }
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params

        # Parse query parameters
        entity_type = params.get("entity_type")
        action = params.get("action")
        entity_id_str = params.get("entity_id")
        actor = params.get("actor")
        since = parse_datetime_param(params, "since")
        until = parse_datetime_param(params, "until")
        limit = parse_int_param(params, "limit", 50)
        offset = parse_int_param(params, "offset", 0)

        # Validate limit
        if limit < 1 or limit > 100:
            return JSONResponse(
                {"error": "limit must be between 1 and 100"},
                status_code=400
            )

        # Validate offset
        if offset < 0:
            return JSONResponse(
                {"error": "offset must be >= 0"},
                status_code=400
            )

        # Parse entity_id if provided
        entity_id = None
        if entity_id_str:
            try:
                entity_id = int(entity_id_str)
            except ValueError:
                return JSONResponse(
                    {"error": "entity_id must be an integer"},
                    status_code=400
                )

        # Convert and validate action if provided
        action_enum = None
        if action:
            try:
                action_enum = ActionType(action)
            except ValueError:
                valid = ", ".join(a.value for a in ActionType)
                return JSONResponse(
                    {"error": f"Invalid action: {action}. Valid values: {valid}"},
                    status_code=400
                )

        # Convert and validate entity_type if provided
        entity_type_enum = None
        if entity_type:
            try:
                entity_type_enum = EntityType(entity_type)
            except ValueError:
                valid = ", ".join(e.value for e in EntityType)
                return JSONResponse(
                    {"error": f"Invalid entity_type: {entity_type}. Valid values: {valid}"},
                    status_code=400
                )

        # Convert and validate actor if provided
        actor_enum = None
        if actor:
            try:
                actor_enum = ActorType(actor)
            except ValueError:
                valid = ", ".join(a.value for a in ActorType)
                return JSONResponse(
                    {"error": f"Invalid actor: {actor}. Valid values: {valid}"},
                    status_code=400
                )

        response = await mcp.activity_service.get_activity(
            user_id=user.id,
            entity_type=entity_type_enum,
            action=action_enum,
            entity_id=entity_id,
            actor=actor_enum,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(response.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/activity/{entity_type}/{entity_id}", methods=["GET"])
    async def get_entity_history(request: Request) -> JSONResponse:
        """
        Get activity history for a specific entity.

        Path params:
            entity_type: Entity type (memory, project, document, code_artifact, entity)
            entity_id: Entity ID

        Query params:
            limit: Maximum results (1-100, default 50)
            offset: Skip N results for pagination (default 0)

        Returns:
            {
                "events": [...],
                "total": int,
                "limit": int,
                "offset": int
            }
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        entity_type_str = request.path_params["entity_type"]
        entity_id_str = request.path_params["entity_id"]

        # Convert and validate entity_type (excluding "link" for entity history)
        valid_for_history = {EntityType.MEMORY, EntityType.PROJECT, EntityType.DOCUMENT,
                            EntityType.CODE_ARTIFACT, EntityType.ENTITY}
        try:
            entity_type_enum = EntityType(entity_type_str)
            if entity_type_enum not in valid_for_history:
                raise ValueError("not valid for history")
        except ValueError:
            valid = ", ".join(e.value for e in valid_for_history)
            return JSONResponse(
                {"error": f"Invalid entity_type: {entity_type_str}. Valid values: {valid}"},
                status_code=400
            )

        # Parse entity_id
        try:
            entity_id = int(entity_id_str)
        except ValueError:
            return JSONResponse(
                {"error": "entity_id must be an integer"},
                status_code=400
            )

        params = request.query_params
        limit = parse_int_param(params, "limit", 50)
        offset = parse_int_param(params, "offset", 0)

        # Validate limit
        if limit < 1 or limit > 100:
            return JSONResponse(
                {"error": "limit must be between 1 and 100"},
                status_code=400
            )

        response = await mcp.activity_service.get_entity_history(
            user_id=user.id,
            entity_type=entity_type_enum,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(response.model_dump(mode="json"))
