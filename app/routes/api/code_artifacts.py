"""
REST API endpoints for Code Artifact operations.

Phase 3c of the Web UI foundation (Issue #3).
Provides CRUD operations for code artifacts.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.code_artifact_models import (
    CodeArtifactCreate,
    CodeArtifactUpdate,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register code artifact REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/code-artifacts", methods=["GET"])
    async def list_code_artifacts(request: Request) -> JSONResponse:
        """
        List code artifacts with optional filtering.

        Query params:
            project_id: Filter by project
            language: Filter by programming language
            tags: Comma-separated tags (OR logic)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        language = params.get("language")
        tags_str = params.get("tags")

        project_id = None
        if project_id_str:
            try:
                project_id = int(project_id_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid project_id: {project_id_str}. Must be an integer."},
                    status_code=400
                )
        tags = [t.strip() for t in tags_str.split(",")] if tags_str else None

        artifacts = await mcp.code_artifact_service.list_code_artifacts(
            user_id=user.id,
            project_id=project_id,
            language=language,
            tags=tags
        )

        return JSONResponse({
            "code_artifacts": [a.model_dump(mode="json") for a in artifacts],
            "total": len(artifacts)
        })

    @mcp.custom_route("/api/v1/code-artifacts/{artifact_id}", methods=["GET"])
    async def get_code_artifact(request: Request) -> JSONResponse:
        """Get a single code artifact by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        artifact_id = int(request.path_params["artifact_id"])

        try:
            artifact = await mcp.code_artifact_service.get_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Code artifact not found"}, status_code=404)

        return JSONResponse(artifact.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/code-artifacts", methods=["POST"])
    async def create_code_artifact(request: Request) -> JSONResponse:
        """Create a new code artifact."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            artifact_data = CodeArtifactCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        artifact = await mcp.code_artifact_service.create_code_artifact(
            user_id=user.id,
            artifact_data=artifact_data
        )

        return JSONResponse(artifact.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/code-artifacts/{artifact_id}", methods=["PUT"])
    async def update_code_artifact(request: Request) -> JSONResponse:
        """Update an existing code artifact."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        artifact_id = int(request.path_params["artifact_id"])

        try:
            body = await request.json()
            update_data = CodeArtifactUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            artifact = await mcp.code_artifact_service.update_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id,
                artifact_data=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Code artifact not found"}, status_code=404)

        return JSONResponse(artifact.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/code-artifacts/{artifact_id}", methods=["DELETE"])
    async def delete_code_artifact(request: Request) -> JSONResponse:
        """Delete a code artifact."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        artifact_id = int(request.path_params["artifact_id"])

        try:
            success = await mcp.code_artifact_service.delete_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Code artifact not found"}, status_code=404)

        if not success:
            return JSONResponse({"error": "Code artifact not found"}, status_code=404)

        return JSONResponse({"success": True})
