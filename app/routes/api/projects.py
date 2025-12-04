"""
REST API endpoints for Project operations.

Phase 3a of the Web UI foundation (Issue #3).
Provides CRUD operations for projects.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.project_models import (
    ProjectCreate,
    ProjectUpdate,
    ProjectStatus,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register project REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/projects", methods=["GET"])
    async def list_projects(request: Request) -> JSONResponse:
        """
        List projects with optional filtering.

        Query params:
            status: Filter by status (active, archived, completed)
            repo_name: Filter by repository name
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        status_str = params.get("status")
        repo_name = params.get("repo_name")

        # Parse status enum if provided
        status = None
        if status_str:
            try:
                status = ProjectStatus(status_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid status: {status_str}. Valid values: active, archived, completed"},
                    status_code=400
                )

        projects = await mcp.project_service.list_projects(
            user_id=user.id,
            status=status,
            repo_name=repo_name
        )

        return JSONResponse({
            "projects": [p.model_dump(mode="json") for p in projects],
            "total": len(projects)
        })

    @mcp.custom_route("/api/v1/projects/{project_id}", methods=["GET"])
    async def get_project(request: Request) -> JSONResponse:
        """Get a single project by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        project_id = int(request.path_params["project_id"])

        project = await mcp.project_service.get_project(
            user_id=user.id,
            project_id=project_id
        )

        if not project:
            return JSONResponse({"error": "Project not found"}, status_code=404)

        return JSONResponse(project.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/projects", methods=["POST"])
    async def create_project(request: Request) -> JSONResponse:
        """Create a new project."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            project_data = ProjectCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        project = await mcp.project_service.create_project(
            user_id=user.id,
            project_data=project_data
        )

        return JSONResponse(project.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/projects/{project_id}", methods=["PUT"])
    async def update_project(request: Request) -> JSONResponse:
        """Update an existing project."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        project_id = int(request.path_params["project_id"])

        try:
            body = await request.json()
            update_data = ProjectUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            project = await mcp.project_service.update_project(
                user_id=user.id,
                project_id=project_id,
                project_data=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Project not found"}, status_code=404)

        if not project:
            return JSONResponse({"error": "Project not found"}, status_code=404)

        return JSONResponse(project.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/projects/{project_id}", methods=["DELETE"])
    async def delete_project(request: Request) -> JSONResponse:
        """Delete a project (preserves associated memories)."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        project_id = int(request.path_params["project_id"])

        try:
            success = await mcp.project_service.delete_project(
                user_id=user.id,
                project_id=project_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Project not found"}, status_code=404)

        if not success:
            return JSONResponse({"error": "Project not found"}, status_code=404)

        return JSONResponse({"success": True})
