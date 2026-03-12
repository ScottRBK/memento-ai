"""
REST API endpoints for Plan operations.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.plan_models import PlanCreate, PlanUpdate, PlanStatus
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError, InvalidStateTransitionError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register plan REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/plans", methods=["GET"])
    async def list_plans(request: Request) -> JSONResponse:
        """List plans with optional filtering."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        status_str = params.get("status")

        project_id = int(project_id_str) if project_id_str else None
        status = None
        if status_str:
            try:
                status = PlanStatus(status_str)
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid status: {status_str}. Valid: draft, active, completed, archived"},
                    status_code=400,
                )

        plans = await mcp.plan_service.list_plans(
            user_id=user.id, project_id=project_id, status=status
        )
        return JSONResponse({
            "plans": [p.model_dump(mode="json") for p in plans],
            "total": len(plans),
        })

    @mcp.custom_route("/api/v1/plans/{plan_id}", methods=["GET"])
    async def get_plan(request: Request) -> JSONResponse:
        """Get a single plan by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        plan_id = int(request.path_params["plan_id"])
        plan = await mcp.plan_service.get_plan(user_id=user.id, plan_id=plan_id)
        if not plan:
            return JSONResponse({"error": "Plan not found"}, status_code=404)
        return JSONResponse(plan.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/plans", methods=["POST"])
    async def create_plan(request: Request) -> JSONResponse:
        """Create a new plan."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            plan_data = PlanCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        plan = await mcp.plan_service.create_plan(user_id=user.id, plan_data=plan_data)
        return JSONResponse(plan.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/plans/{plan_id}", methods=["PUT"])
    async def update_plan(request: Request) -> JSONResponse:
        """Update an existing plan."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        plan_id = int(request.path_params["plan_id"])

        try:
            body = await request.json()
            update_data = PlanUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            plan = await mcp.plan_service.update_plan(
                user_id=user.id, plan_id=plan_id, plan_data=update_data
            )
        except InvalidStateTransitionError as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        except NotFoundError:
            return JSONResponse({"error": "Plan not found"}, status_code=404)

        if not plan:
            return JSONResponse({"error": "Plan not found"}, status_code=404)
        return JSONResponse(plan.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/plans/{plan_id}", methods=["DELETE"])
    async def delete_plan(request: Request) -> JSONResponse:
        """Delete a plan (cascades to tasks/criteria/deps)."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        plan_id = int(request.path_params["plan_id"])
        success = await mcp.plan_service.delete_plan(user_id=user.id, plan_id=plan_id)
        if not success:
            return JSONResponse({"error": "Plan not found"}, status_code=404)
        return JSONResponse({"success": True})
