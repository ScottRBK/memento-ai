"""
MCP Project Tools - FastMCP tool definitions for project operations
"""

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import ValidationError


from app.models.project_models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectStatus,
    ProjectType
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import filter_none_values


logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
    """Register the project tools - services accessed via context at call time"""

    @mcp.tool()
    async def create_project(
        name: str,
        description: str,
        project_type: ProjectType,
        ctx: Context,
        status: ProjectStatus = ProjectStatus.ACTIVE,
        repo_name: str = None,
        notes: str = None,
    ) -> Project:
        """
        Create new project for organizing memories and knowledge

        WHAT: Creates project with name + metadata (description, type, status, repo, notes).
        Projects organize memories, code artifacts, and documents by context.

        WHEN: User wants to start new project, organize memories by context, or set up workspace.
        Queries: "Create project for X", "Start project Y", "Set up project to track Z".

        BEHAVIOR: Creates project with provided metadata. Status defaults to 'active' if not
        specified. Generated fields (id, timestamps) added automatically. Projects scope memory
        searches and organize knowledge by context.

        NOT-USE: Updating projects (use update_project), listing (use list_projects), or linking
        memories (happens automatically via memory tools).

        EXAMPLES:
        create_project(
            name="forgetful",
            description="MIT-licensed memory service implementing atomic memory principles",
            project_type="development",
            status="active",
            repo_name="scottrbk/forgetful"
        )

        Args:
            name: Project name (max 500 chars) - short identifier
            description: Purpose/scope overview (required, max ~5000 chars)
            project_type: Project category (required). Options: personal, work, learning,
                development, infrastructure, template, product, marketing, finance,
                documentation, development-environment, third-party-library, open-source
            status: Project lifecycle status (default: active). Options: active, archived, completed
            repo_name: GitHub repository in 'owner/repo' format (optional, e.g., 'scottrbk/forgetful')
            notes: Workflow notes, setup instructions (optional, max ~4000 chars)
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete Project with id, timestamps, and memory_count
        """

        logger.info("MCP Tool Called -> create_project", extra={
            "project_name": name[:50],
            "project_type": project_type.value
        })

        user = await get_user_from_auth(ctx)

        try:
            # Build project creation data
            project_data = ProjectCreate(
                name=name,
                description=description,
                project_type=project_type,
                status=status,
                repo_name=repo_name,
                notes=notes
            )

            # Access project service via FastMCP context
            project_service = ctx.fastmcp.project_service
            project = await project_service.create_project(
                user_id=user.id,
                project_data=project_data
            )

            logger.info("MCP Tool Call -> create_project completed", extra={
                "user_id": str(user.id),
                "project_id": project.id,
                "project_name": project.name
            })

            return project

        except NotFoundError as e:
            logger.debug("MCP Tool - create_project validation error", extra={
                "user_id": str(user.id),
                "project_name": name[:50],
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - create_project validation error", extra={
                "user_id": str(user.id),
                "project_name": name[:50],
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool - create_project failed", exc_info=True, extra={
                "user_id": str(user.id),
                "project_name": name[:50],
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Project creation failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def update_project(
        project_id: int,
        ctx: Context,
        name: str = None,
        description: str = None,
        project_type: ProjectType = None,
        status: ProjectStatus = None,
        repo_name: str = None,
        notes: str = None,
    ) -> Project:
        """
        Update project metadata (PATCH semantics)

        WHAT: Updates project fields using PATCH semantics (only provided fields updated).
        None values mean "don't change this field".

        WHEN: User wants to modify project info, change status, update notes.
        Queries: "Archive project X", "Update notes for Y", "Change project Z to completed".

        BEHAVIOR: Updates specified fields only (PATCH). None=ignored, keeps current value.
        At least one field should be provided. Returns complete updated project. Validates
        project_id exists and belongs to user. Doesn't affect linked memories.

        NOT-USE: Creating (use create_project), deleting (use delete_project), or linking
        memories (use link_memory_to_project in memory tools).

        EXAMPLES:
        # Archive project
        update_project(project_id=5, status="archived")

        # Update description after refactor
        update_project(project_id=5, description="New description after refactoring auth system")

        # Change repository
        update_project(project_id=5, repo_name="newowner/newrepo")

        Args:
            project_id: Project ID to update (required)
            name: New project name (optional, unchanged if null)
            description: New description (optional, unchanged if null)
            project_type: New project type (optional, unchanged if null)
            status: New lifecycle status (optional, unchanged if null). Options: active, archived, completed
            repo_name: New repository 'owner/repo' format (optional, unchanged if null)
            notes: New notes (optional, unchanged if null, max ~4000 chars)
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Updated Project with all fields
        """

        logger.info("MCP Tool Called -> update_project", extra={
            "project_id": project_id
        })

        user = await get_user_from_auth(ctx)

        try:
            # Build update dict, filtering out None values
            update_dict = filter_none_values(
                name=name,
                description=description,
                project_type=project_type,
                status=status,
                repo_name=repo_name,
                notes=notes
            )

            if not update_dict:
                raise ToolError("VALIDATION_ERROR: At least one field must be provided for update")

            # Build project update data
            project_data = ProjectUpdate(**update_dict)

            # Access project service via FastMCP context
            project_service = ctx.fastmcp.project_service
            project = await project_service.update_project(
                user_id=user.id,
                project_id=project_id,
                project_data=project_data
            )

            if not project:
                raise NotFoundError(f"Project with id {project_id} not found")

            logger.info("MCP Tool Call -> update_project completed", extra={
                "user_id": str(user.id),
                "project_id": project.id,
                "updated_fields": list(update_dict.keys())
            })

            return project

        except NotFoundError as e:
            logger.debug("MCP Tool - update_project not found", extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - update_project validation error", extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool - update_project failed", exc_info=True, extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Project update failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def delete_project(
        project_id: int,
        ctx: Context
    ) -> dict:
        """
        Delete project while preserving linked memories

        WHAT: Permanently deletes project metadata (name, description, notes) and project-memory
        associations. IMPORTANT: Memories are preserved and accessible via general queries - only
        container deleted. Cannot be undone.

        WHEN: User wants to remove unneeded project, clean up, or delete mistake.
        Queries: "Delete project X", "Remove project Y", "Don't need project Z anymore".

        BEHAVIOR: Permanently deletes project metadata and associations. Linked memories, code
        artifacts, and documents preserved and remain accessible. Cannot be undone.

        NOT-USE: Temporary pause (use update_project status='archived'), deleting memories
        (use mark_memory_obsolete - this only deletes project container, not knowledge).

        EXAMPLES:
        delete_project(project_id=5)

        Args:
            project_id: Project ID to delete (required)
            ctx: Context (automatically injected by FastMCP)

        Returns:
            {"success": bool, "message": str, "project_id": int}
        """

        logger.info("MCP Tool Called -> delete_project", extra={
            "project_id": project_id
        })

        user = await get_user_from_auth(ctx)

        try:
            # Access project service via FastMCP context
            project_service = ctx.fastmcp.project_service
            success = await project_service.delete_project(
                user_id=user.id,
                project_id=project_id
            )

            if not success:
                raise NotFoundError(f"Project with id {project_id} not found")

            logger.info("MCP Tool Call -> delete_project completed", extra={
                "user_id": str(user.id),
                "project_id": project_id
            })

            return {
                "success": True,
                "message": f"Project {project_id} deleted successfully",
                "project_id": project_id
            }

        except NotFoundError as e:
            logger.debug("MCP Tool - delete_project not found", extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except Exception as e:
            logger.error("MCP Tool - delete_project failed", exc_info=True, extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Project deletion failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def list_projects(
        ctx: Context,
        status: ProjectStatus = None,
        repo_name: str = None,
    ) -> dict:
        """
        List projects with optional status/repository filtering

        WHAT: Returns project summaries (excludes heavy text fields like description/notes to
        save tokens). Filters by status/repo_name if provided; returns all projects if not.

        WHEN: User wants to browse projects or filter by status (active/archived/completed)
        or repository. Queries: "What projects do I have?", "Show active projects",
        "List projects for repo X".

        BEHAVIOR: Returns lightweight project summaries (id, name, type, status, repo_name,
        memory_count). Filters by status/repo_name if provided; all projects if not.
        Ordered by creation time (newest first).

        NOT-USE: Single project details (use get_project), creating (use create_project),
        or searching memories (use query_project_memories).

        EXAMPLES:
        # List all projects
        list_projects()

        # List active projects only
        list_projects(status="active")

        # List projects for specific repository
        list_projects(repo_name="scottrbk/forgetful")

        Args:
            status: Filter by project status (optional). Options: active, archived, completed.
                None returns all statuses.
            repo_name: Filter by repository name (optional, e.g., "scottrbk/forgetful").
                None returns all repos.
            ctx: Context (automatically injected by FastMCP)

        Returns:
            {
                "projects": List[ProjectSummary],
                "total_count": int,
                "status_filter": str | None,
                "repo_name_filter": str | None
            }
        """

        logger.info("MCP Tool Called -> list_projects", extra={
            "status": status.value if status else None,
            "repo_name": repo_name
        })

        user = await get_user_from_auth(ctx)

        try:
            # Access project service via FastMCP context
            project_service = ctx.fastmcp.project_service
            projects = await project_service.list_projects(
                user_id=user.id,
                status=status,
                repo_name=repo_name
            )

            logger.info("MCP Tool Call -> list_projects completed", extra={
                "user_id": str(user.id),
                "total_count": len(projects)
            })

            return {
                "projects": projects,
                "total_count": len(projects),
                "status_filter": status.value if status else None,
                "repo_name_filter": repo_name
            }

        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - list_projects validation error", extra={
                "user_id": str(user.id),
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool - list_projects failed", exc_info=True, extra={
                "user_id": str(user.id),
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Project listing failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def get_project(
        project_id: int,
        ctx: Context
    ) -> Project:
        """
        Retrieve complete project details by ID

        WHAT: Returns full project information including description, notes, relationships,
        and memory count.

        WHEN: User needs full project information or asks about specific project.
        Queries: "Show me project X", "Get details for project Y", "What's in project Z?".
        Typically after list_projects to drill into specific project.

        BEHAVIOR: Returns complete project (id, name, description, type, status, repository,
        notes, timestamps, memory_count). Error if not found or wrong user.

        NOT-USE: Listing projects (use list_projects), searching memories (use query_memory
        with project_ids), or creating/updating (use create_project/update_project).

        EXAMPLES:
        get_project(project_id=5)

        Args:
            project_id: Project ID to retrieve (required)
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete Project with all fields including description and notes
        """

        logger.info("MCP Tool Called -> get_project", extra={
            "project_id": project_id
        })

        user = await get_user_from_auth(ctx)

        try:
            # Access project service via FastMCP context
            project_service = ctx.fastmcp.project_service
            project = await project_service.get_project(
                user_id=user.id,
                project_id=project_id
            )

            if not project:
                raise NotFoundError(f"Project with id {project_id} not found")

            logger.info("MCP Tool Call -> get_project completed", extra={
                "user_id": str(user.id),
                "project_id": project.id,
                "project_name": project.name
            })

            return project

        except NotFoundError as e:
            logger.debug("MCP Tool - get_project not found", extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except Exception as e:
            logger.error("MCP Tool - get_project failed", exc_info=True, extra={
                "user_id": str(user.id),
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Project retrieval failed - {type(e).__name__}: {str(e)}")
