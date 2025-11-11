from typing import Protocol, List
from uuid import UUID

from app.models.project_models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectSummary,
    ProjectStatus
)


class ProjectRepository(Protocol):
    """Contract for Project Repository operations

    Defines the interface that project repository implementations must follow.
    Enables dependency inversion - service layer depends on this protocol,
    not concrete repository implementations.
    """

    async def list_projects(
        self,
        user_id: UUID,
        status: ProjectStatus | None = None,
        repo_name: str | None = None
    ) -> List[ProjectSummary]:
        """List projects with optional filtering

        Args:
            user_id: User ID for RLS (row-level security)
            status: Optional filter by project status (active/archived/completed)
            repo_name: Optional filter by repository name

        Returns:
            List of ProjectSummary objects matching filters
        """
        ...

    async def get_project_by_id(
        self,
        user_id: UUID,
        project_id: int
    ) -> Project | None:
        """Get single project by ID

        Args:
            user_id: User ID for RLS
            project_id: Project ID to retrieve

        Returns:
            Project if found, None otherwise
        """
        ...

    async def create_project(
        self,
        user_id: UUID,
        project_data: ProjectCreate
    ) -> Project:
        """Create new project

        Args:
            user_id: User ID for RLS
            project_data: Project creation data

        Returns:
            Created Project with generated ID and timestamps
        """
        ...

    async def update_project(
        self,
        user_id: UUID,
        project_id: int,
        project_data: ProjectUpdate
    ) -> Project:
        """Update existing project

        Args:
            user_id: User ID for RLS
            project_id: Project ID to update
            project_data: Project update data (PATCH semantics)

        Returns:
            Updated Project

        Raises:
            NotFoundError: If project doesn't exist
        """
        ...

    async def delete_project(
        self,
        user_id: UUID,
        project_id: int
    ) -> bool:
        """Delete project

        Removes project metadata. Linked memories, code artifacts, and documents
        are preserved (associations removed, entities remain).

        Args:
            user_id: User ID for RLS
            project_id: Project ID to delete

        Returns:
            True if deleted, False if not found
        """
        ...
