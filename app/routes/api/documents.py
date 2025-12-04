"""
REST API endpoints for Document operations.

Phase 3b of the Web UI foundation (Issue #3).
Provides CRUD operations for documents.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import ValidationError
import logging

from app.models.document_models import (
    DocumentCreate,
    DocumentUpdate,
)
from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register document REST routes with FastMCP"""

    @mcp.custom_route("/api/v1/documents", methods=["GET"])
    async def list_documents(request: Request) -> JSONResponse:
        """
        List documents with optional filtering.

        Query params:
            project_id: Filter by project
            document_type: Filter by document type
            tags: Comma-separated tags (OR logic)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        document_type = params.get("document_type")
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

        documents = await mcp.document_service.list_documents(
            user_id=user.id,
            project_id=project_id,
            document_type=document_type,
            tags=tags
        )

        return JSONResponse({
            "documents": [d.model_dump(mode="json") for d in documents],
            "total": len(documents)
        })

    @mcp.custom_route("/api/v1/documents/{document_id}", methods=["GET"])
    async def get_document(request: Request) -> JSONResponse:
        """Get a single document by ID."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        document_id = int(request.path_params["document_id"])

        try:
            document = await mcp.document_service.get_document(
                user_id=user.id,
                document_id=document_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Document not found"}, status_code=404)

        return JSONResponse(document.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/documents", methods=["POST"])
    async def create_document(request: Request) -> JSONResponse:
        """Create a new document."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        try:
            body = await request.json()
            document_data = DocumentCreate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        document = await mcp.document_service.create_document(
            user_id=user.id,
            document_data=document_data
        )

        return JSONResponse(document.model_dump(mode="json"), status_code=201)

    @mcp.custom_route("/api/v1/documents/{document_id}", methods=["PUT"])
    async def update_document(request: Request) -> JSONResponse:
        """Update an existing document."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        document_id = int(request.path_params["document_id"])

        try:
            body = await request.json()
            update_data = DocumentUpdate(**body)
        except ValidationError as e:
            return JSONResponse({"error": e.errors()}, status_code=400)

        try:
            document = await mcp.document_service.update_document(
                user_id=user.id,
                document_id=document_id,
                document_data=update_data
            )
        except NotFoundError:
            return JSONResponse({"error": "Document not found"}, status_code=404)

        return JSONResponse(document.model_dump(mode="json"))

    @mcp.custom_route("/api/v1/documents/{document_id}", methods=["DELETE"])
    async def delete_document(request: Request) -> JSONResponse:
        """Delete a document."""
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        document_id = int(request.path_params["document_id"])

        try:
            success = await mcp.document_service.delete_document(
                user_id=user.id,
                document_id=document_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Document not found"}, status_code=404)

        if not success:
            return JSONResponse({"error": "Document not found"}, status_code=404)

        return JSONResponse({"success": True})
