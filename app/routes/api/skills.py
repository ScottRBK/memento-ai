"""
REST API endpoints for Skill operations.

Provides CRUD operations, semantic search, and import/export
for skills (procedural memory following the Agent Skills standard).
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.skill_models import (
    SkillCreate,
    SkillUpdate,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register skill REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/skills", methods=["POST"])
    async def create_skill(request: Request) -> JSONResponse:
        """Create a new skill."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            skill_data = SkillCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        skill = await mcp.skill_service.create_skill(
            user_id=user.id,
            skill_data=skill_data
        )

        return JSONResponse(skill.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/skills", methods=["GET"])
    async def list_skills(request: Request) -> JSONResponse:
        """
        List skills with optional filtering.

        Query params:
            project_id: Filter by project
            tags: Comma-separated tags (OR logic)
            importance_threshold: Minimum importance level
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        tags_str = params.get("tags")
        importance_threshold_str = params.get("importance_threshold")

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

        importance_threshold = None
        if importance_threshold_str:
            try:
                importance_threshold = int(importance_threshold_str)
            except ValueError:
                msg = (
                    f"Invalid importance_threshold: "
                    f"{importance_threshold_str}. "
                    f"Must be an integer."
                )
                return JSONResponse(
                    {"error": msg},
                    status_code=400,
                )

        skills = await mcp.skill_service.list_skills(
            user_id=user.id,
            project_id=project_id,
            tags=tags,
            importance_threshold=importance_threshold,
        )

        return JSONResponse({
            "skills": [s.model_dump(mode="json") for s in skills],
            "total": len(skills)
        })

    @mcp.custom_route("/api/v1/skills/search", methods=["GET"])
    async def search_skills(request: Request) -> JSONResponse:
        """
        Semantic search for skills.

        Query params:
            query: Search query string (required)
            k: Number of results (default: 5)
            project_id: Optional filter by project
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        query = params.get("query")
        if not query:
            return JSONResponse(
                {"error": "query parameter is required"},
                status_code=400
            )

        k_str = params.get("k", "5")
        try:
            k = int(k_str)
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid k: {k_str}. Must be an integer."},
                status_code=400
            )

        project_id_str = params.get("project_id")
        project_id = None
        if project_id_str:
            try:
                project_id = int(project_id_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid project_id: {project_id_str}. Must be an integer."},
                    status_code=400
                )

        skills = await mcp.skill_service.search_skills(
            user_id=user.id,
            query=query,
            k=k,
            project_id=project_id,
        )

        return JSONResponse({
            "skills": [s.model_dump(mode="json") for s in skills],
            "query": query,
            "total": len(skills)
        })

    @mcp.custom_route("/api/v1/skills/{skill_id}", methods=["GET"])
    async def get_skill(request: Request) -> JSONResponse:
        """Get a single skill by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        skill_id = int(request.path_params["skill_id"])

        try:
            skill = await mcp.skill_service.get_skill(
                user_id=user.id,
                skill_id=skill_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Skill not found"}, status_code=404)

        return JSONResponse(skill.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/skills/{skill_id}", methods=["PUT"])
    async def update_skill(request: Request) -> JSONResponse:
        """Update an existing skill."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        skill_id = int(request.path_params["skill_id"])

        try:
            body = await request.json()
            update_data = SkillUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        try:
            skill = await mcp.skill_service.update_skill(
                user_id=user.id,
                skill_id=skill_id,
                skill_data=update_data,
            )
        except NotFoundError:
            return JSONResponse({"error": "Skill not found"}, status_code=404)

        return JSONResponse(skill.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/skills/{skill_id}", methods=["DELETE"])
    async def delete_skill(request: Request) -> JSONResponse:
        """Delete a skill."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        skill_id = int(request.path_params["skill_id"])

        try:
            success = await mcp.skill_service.delete_skill(
                user_id=user.id,
                skill_id=skill_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Skill not found"}, status_code=404)

        if not success:
            return JSONResponse({"error": "Skill not found"}, status_code=404)

        return JSONResponse({"success": True})

    @mcp.custom_route("/api/v1/skills/import", methods=["POST"])
    async def import_skill(request: Request) -> JSONResponse:
        """
        Import a skill from Agent Skills markdown format.

        Body:
            skill_md: Raw SKILL.md content with YAML frontmatter (required)
            project_id: Optional project association
            importance: Optional importance level (default: 7)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
        except (ValueError, KeyError):
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        skill_md = body.get("skill_md")
        if not skill_md:
            return JSONResponse(
                {"error": "skill_md field is required"},
                status_code=400
            )

        project_id = body.get("project_id")
        importance = body.get("importance", 7)

        try:
            skill = await mcp.skill_service.import_skill(
                user_id=user.id,
                skill_md_content=skill_md,
                project_id=project_id,
                importance=importance,
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except ValidationError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        return JSONResponse(skill.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/skills/{skill_id}/export", methods=["GET"])
    async def export_skill(request: Request) -> JSONResponse:
        """Export a skill to Agent Skills markdown format (SKILL.md)."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        skill_id = int(request.path_params["skill_id"])

        try:
            skill_md = await mcp.skill_service.export_skill(
                user_id=user.id,
                skill_id=skill_id,
            )
        except NotFoundError:
            return JSONResponse({"error": "Skill not found"}, status_code=404)

        return JSONResponse({"skill_md": skill_md})
