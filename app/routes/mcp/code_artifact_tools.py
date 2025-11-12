"""
MCP Code Artifact tools - FastMCP tool definitions for code artifact operations
"""
from typing import List

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import filter_none_values

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register code artifact tools - services accessed via context at call time"""

    @mcp.tool()
    async def create_code_artifact(
        title: str,
        description: str,
        code: str,
        language: str,
        ctx: Context,
        tags: List[str] = None,
        project_id: int = None,
    ) -> CodeArtifact:
        """
        Create code artifact for storing reusable code snippets and patterns.

        WHAT: Stores code implementations, examples, and patterns with metadata.
        Projects and memories can reference these for documentation and knowledge sharing.

        WHEN: When documenting reusable code patterns, implementations, or solutions
        that should be referenced by memories or shared across projects. Examples:
        - Authentication middleware
        - Utility functions
        - API patterns
        - SQL queries
        - Configuration templates

        BEHAVIOR: Creates code artifact with provided metadata. Can be associated with
        a project immediately via project_id. Returns complete artifact with generated ID.
        To link to memories, use create_memory or update_memory with code_artifact_ids=[artifact_id].

        NOT-USE: For inline code examples in memories (use memory content directly),
        temporary snippets, or code that doesn't represent reusable patterns.

        EXAMPLES:
        create_code_artifact(
            title="FastAPI JWT Middleware",
            description="Async-safe JWT validation for FastMCP tools",
            code="@app.middleware('http')\nasync def jwt_middleware(request, call_next):\n    ...",
            language="python",
            tags=["fastapi", "auth", "jwt"]
        )

        create_code_artifact(
            title="User Activity Report Query",
            description="PostgreSQL query for daily active user metrics",
            code="SELECT DATE(created_at) as date, COUNT(DISTINCT user_id) as dau\nFROM events\nWHERE event_type = 'login'\nGROUP BY DATE(created_at);",
            language="sql",
            tags=["analytics", "reporting", "postgresql"]
        )

        Args:
            title: Artifact title (max 500 chars) - searchable identifier
            description: Purpose and use case - what does this code do?
            code: Complete code snippet or implementation
            language: Programming language. Use full names (e.g., 'python' not 'py', 'javascript' not 'js')
            tags: Optional tags for discovery and categorization (max 10)
            project_id: Optional project ID for immediate association
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete CodeArtifact with ID, timestamps, and metadata
        """

        logger.info("MCP Tool Called -> create_code_artifact", extra={
            "title": title[:50],
            "language": language
        })

        user = await get_user_from_auth(ctx)

        try:
            artifact_data = CodeArtifactCreate(
                title=title,
                description=description,
                code=code,
                language=language,
                tags=tags or [],
                project_id=project_id
            )
        except ValidationError as e:
            raise ToolError(f"Invalid code artifact data: {e}")

        try:
            artifact_service = ctx.fastmcp.code_artifact_service
            artifact = await artifact_service.create_code_artifact(
                user_id=user.id,
                artifact_data=artifact_data
            )

            return artifact

        except Exception as e:
            logger.error("Failed to create code artifact", exc_info=True)
            raise ToolError(f"Failed to create code artifact: {str(e)}")

    @mcp.tool()
    async def get_code_artifact(
        artifact_id: int,
        ctx: Context
    ) -> CodeArtifact:
        """
        Retrieve code artifact by ID with complete details.

        WHEN: You need the full code implementation and metadata for a specific artifact.
        Common after listing artifacts or when a memory references an artifact ID.

        BEHAVIOR: Returns complete artifact including full code content, description,
        and metadata. Ownership verified automatically.

        NOT-USE: For browsing multiple artifacts (use list_code_artifacts).

        Args:
            artifact_id: Unique code artifact ID
            ctx: Context (automatically injected)

        Returns:
            Complete CodeArtifact with code, description, metadata

        Raises:
            ToolError if artifact not found or access denied
        """

        logger.info("MCP Tool Called -> get_code_artifact", extra={
            "artifact_id": artifact_id
        })

        user = await get_user_from_auth(ctx)

        try:
            artifact_service = ctx.fastmcp.code_artifact_service
            artifact = await artifact_service.get_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id
            )

            return artifact

        except NotFoundError:
            raise ToolError(f"Code artifact {artifact_id} not found")
        except Exception as e:
            logger.error("Failed to get code artifact", exc_info=True)
            raise ToolError(f"Failed to retrieve code artifact: {str(e)}")

    @mcp.tool()
    async def list_code_artifacts(
        ctx: Context,
        project_id: int = None,
        language: str = None,
        tags: List[str] = None,
    ) -> dict:
        """
        List code artifacts with optional filtering.

        WHEN: Browsing available code artifacts, searching for specific patterns,
        or discovering artifacts by technology/category.

        BEHAVIOR: Returns lightweight summaries (excludes full code content) sorted
        by creation date (newest first). Filters can be combined:
        - project_id: Only artifacts in this project
        - language: Only artifacts in this language (case-insensitive)
        - tags: Artifacts with ANY of these tags

        NOT-USE: When you already have an artifact ID and need full code (use get_code_artifact).

        EXAMPLES:
        - All Python artifacts: list_code_artifacts(language="python")
        - Auth-related in project: list_code_artifacts(project_id=5, tags=["auth"])
        - SQL queries: list_code_artifacts(language="sql")

        Args:
            project_id: Optional filter by project
            language: Optional filter by language (e.g., 'python', 'javascript', 'sql')
            tags: Optional filter by tags (returns artifacts with ANY of these tags)
            ctx: Context (automatically injected)

        Returns:
            {
                "code_artifacts": List[CodeArtifactSummary],
                "total_count": int,
                "filters": {
                    "project_id": int | None,
                    "language": str | None,
                    "tags": List[str] | None
                }
            }
        """

        logger.info("MCP Tool Called -> list_code_artifacts", extra={
            "project_id": project_id,
            "language": language,
            "tags": tags
        })

        user = await get_user_from_auth(ctx)

        try:
            artifact_service = ctx.fastmcp.code_artifact_service
            artifacts = await artifact_service.list_code_artifacts(
                user_id=user.id,
                project_id=project_id,
                language=language,
                tags=tags
            )

            return {
                "code_artifacts": artifacts,
                "total_count": len(artifacts),
                "filters": {
                    "project_id": project_id,
                    "language": language,
                    "tags": tags
                }
            }

        except Exception as e:
            logger.error("Failed to list code artifacts", exc_info=True)
            raise ToolError(f"Failed to list code artifacts: {str(e)}")

    @mcp.tool()
    async def update_code_artifact(
        artifact_id: int,
        ctx: Context,
        title: str = None,
        description: str = None,
        code: str = None,
        language: str = None,
        tags: List[str] = None,
        project_id: int = None,
    ) -> CodeArtifact:
        """
        Update code artifact (PATCH semantics - only provided fields changed).

        WHEN: Refining code implementations, correcting errors, updating descriptions,
        changing categorization, or associating with different project.

        BEHAVIOR: Updates only the fields you provide. Omitted fields remain unchanged.
        - Omit a field = no change
        - Provide new value = replace
        - tags=[] = clear all tags

        NOT-USE: Creating new artifacts (use create_code_artifact).

        EXAMPLES:
        - Fix typo: update_code_artifact(artifact_id=5, description="Corrected description")
        - Update code: update_code_artifact(artifact_id=5, code="new implementation...")
        - Add tags: update_code_artifact(artifact_id=5, tags=["tag1", "tag2", "tag3"])

        Args:
            artifact_id: Artifact ID to update
            title: New title (unchanged if omitted)
            description: New description (unchanged if omitted)
            code: New code (unchanged if omitted)
            language: New language (unchanged if omitted)
            tags: New tags (unchanged if omitted, empty list [] clears tags)
            project_id: New project association (unchanged if omitted)
            ctx: Context (automatically injected)

        Returns:
            Updated CodeArtifact

        Raises:
            ToolError if artifact not found or update fails
        """

        logger.info("MCP Tool Called -> update_code_artifact", extra={
            "artifact_id": artifact_id
        })

        user = await get_user_from_auth(ctx)

        try:
            # Build update dict, filtering out None values for PATCH semantics
            update_dict = filter_none_values(
                title=title,
                description=description,
                code=code,
                language=language,
                tags=tags,
                project_id=project_id
            )

            # Build update model with only provided fields
            update_data = CodeArtifactUpdate(**update_dict)
        except ValidationError as e:
            raise ToolError(f"Invalid update data: {e}")

        try:
            artifact_service = ctx.fastmcp.code_artifact_service
            artifact = await artifact_service.update_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id,
                artifact_data=update_data
            )

            return artifact

        except NotFoundError:
            raise ToolError(f"Code artifact {artifact_id} not found")
        except Exception as e:
            logger.error("Failed to update code artifact", exc_info=True)
            raise ToolError(f"Failed to update code artifact: {str(e)}")

    @mcp.tool()
    async def delete_code_artifact(
        artifact_id: int,
        ctx: Context
    ) -> dict:
        """
        Delete code artifact (cascades memory associations).

        WHEN: Removing obsolete, incorrect, or no-longer-relevant code artifacts.

        BEHAVIOR: Permanently deletes artifact and removes memory associations.
        Memories themselves are preserved. Cannot be undone.

        NOT-USE: For temporary hiding (no undo available), or updating (use update_code_artifact).

        Args:
            artifact_id: Artifact ID to delete
            ctx: Context (automatically injected)

        Returns:
            Success confirmation with deleted artifact ID

        Raises:
            ToolError if artifact not found
        """

        logger.info("MCP Tool Called -> delete_code_artifact", extra={
            "artifact_id": artifact_id
        })

        user = await get_user_from_auth(ctx)

        try:
            artifact_service = ctx.fastmcp.code_artifact_service
            success = await artifact_service.delete_code_artifact(
                user_id=user.id,
                artifact_id=artifact_id
            )

            if not success:
                raise ToolError(f"Code artifact {artifact_id} not found")

            return {"deleted_id": artifact_id}

        except Exception as e:
            logger.error("Failed to delete code artifact", exc_info=True)
            raise ToolError(f"Failed to delete code artifact: {str(e)}")
