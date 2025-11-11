"""
Project repository for postgres data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import NoResultFound

from app.repositories.postgres.postgres_tables import ProjectsTable
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.models.project_models import (
    Project,
    ProjectCreate,
    ProjectUpdate,
    ProjectSummary,
    ProjectStatus
)
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class PostgresProjectRepository:
    """
    Repository for Project entity operations in Postgres

    Handles CRUD operations for projects with PostgreSQL backend.
    Projects organize memories, code artifacts, and documents by context.
    Simpler than MemoryRepository - no embeddings, auto-linking, or lifecycle.
    """

    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        """Initialize repository with database adapter

        Args:
            db_adapter: PostgreSQL database adapter for session management
        """
        self.db_adapter = db_adapter
        logger.info("Project repository initialized")

    async def list_projects(
        self,
        user_id: UUID,
        status: ProjectStatus | None = None,
        repo_name: str | None = None
    ) -> List[ProjectSummary]:
        """List projects with optional filtering

        Retrieves lightweight project summaries. Filters by status and/or
        repository name if provided. Includes memory_count for each project.

        Args:
            user_id: User ID for RLS (row-level security)
            status: Optional filter by project status
            repo_name: Optional filter by repository name

        Returns:
            List of ProjectSummary objects ordered by created_at desc
        """
        logger.info(
            "Listing projects",
            extra={
                "user_id": str(user_id),
                "status": status.value if status else None,
                "repo_name": repo_name
            }
        )

        async with self.db_adapter.session(user_id) as session:
            # Build base query with eager loading
            stmt = (
                select(ProjectsTable)
                .options(selectinload(ProjectsTable.memories))
                .where(ProjectsTable.user_id == user_id)
            )

            # Apply optional filters
            if status:
                stmt = stmt.where(ProjectsTable.status == status.value)

            if repo_name:
                stmt = stmt.where(ProjectsTable.repo_name == repo_name)

            # Order by creation date (newest first)
            stmt = stmt.order_by(ProjectsTable.created_at.desc())

            # Execute query
            result = await session.execute(stmt)
            projects_orm = result.scalars().all()

            # Convert to ProjectSummary models
            projects = [ProjectSummary.model_validate(p) for p in projects_orm]

            logger.info(
                "Projects retrieved",
                extra={"count": len(projects), "user_id": str(user_id)}
            )

            return projects

    async def get_project_by_id(
        self,
        user_id: UUID,
        project_id: int
    ) -> Project | None:
        """Get single project by ID

        Retrieves complete project details including relationships.

        Args:
            user_id: User ID for RLS
            project_id: Project ID to retrieve

        Returns:
            Project if found, None otherwise
        """
        logger.info(
            "Getting project by ID",
            extra={"user_id": str(user_id), "project_id": project_id}
        )

        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(ProjectsTable)
                .options(selectinload(ProjectsTable.memories))
                .where(
                    ProjectsTable.user_id == user_id,
                    ProjectsTable.id == project_id
                )
            )

            result = await session.execute(stmt)
            project_orm = result.scalar_one_or_none()

            if project_orm:
                logger.info(
                    "Project found",
                    extra={"project_id": project_id, "project_name": project_orm.name}
                )
                return Project.model_validate(project_orm)
            else:
                logger.info(
                    "Project not found",
                    extra={"project_id": project_id, "user_id": str(user_id)}
                )
                return None

    async def create_project(
        self,
        user_id: UUID,
        project_data: ProjectCreate
    ) -> Project:
        """Create new project

        Creates project with provided metadata. Status defaults to 'active'.
        Generated fields (id, timestamps) added automatically.

        Args:
            user_id: User ID for RLS
            project_data: Project creation data

        Returns:
            Created Project with generated ID and timestamps
        """
        logger.info(
            "Creating project",
            extra={
                "user_id": str(user_id),
                "project_name": project_data.name,
                "type": project_data.project_type.value
            }
        )

        async with self.db_adapter.session(user_id) as session:
            # Extract data and create ORM object
            data = project_data.model_dump()
            new_project = ProjectsTable(
                **data,
                user_id=user_id
            )

            # Add and flush to get ID
            session.add(new_project)
            await session.flush()

            # Refresh to load relationships (eager load memories for memory_count)
            await session.refresh(new_project, attribute_names=['memories'])

            # Convert to Pydantic model
            project = Project.model_validate(new_project)

            logger.info(
                "Project created",
                extra={
                    "project_id": project.id,
                    "project_name": project.name,
                    "user_id": str(user_id)
                }
            )

            return project

    async def update_project(
        self,
        user_id: UUID,
        project_id: int,
        project_data: ProjectUpdate
    ) -> Project:
        """Update existing project

        Updates project fields using PATCH semantics (only provided fields updated).

        Args:
            user_id: User ID for RLS
            project_id: Project ID to update
            project_data: Project update data (all fields optional)

        Returns:
            Updated Project

        Raises:
            NotFoundError: If project doesn't exist
        """
        logger.info(
            "Updating project",
            extra={"user_id": str(user_id), "project_id": project_id}
        )

        async with self.db_adapter.session(user_id) as session:
            # Build update dict (exclude unset fields for PATCH semantics)
            update_data = project_data.model_dump(exclude_unset=True)

            if not update_data:
                logger.info("No fields to update")
                # Still need to return the project
                stmt = (
                    select(ProjectsTable)
                    .options(selectinload(ProjectsTable.memories))
                    .where(
                        ProjectsTable.user_id == user_id,
                        ProjectsTable.id == project_id
                    )
                )
                result = await session.execute(stmt)
                project_orm = result.scalar_one_or_none()

                if not project_orm:
                    raise NotFoundError(f"Project with id {project_id} not found")

                return Project.model_validate(project_orm)

            # Add updated timestamp
            update_data['updated_at'] = datetime.now(timezone.utc)

            # Execute update with RETURNING
            stmt = (
                update(ProjectsTable)
                .where(
                    ProjectsTable.user_id == user_id,
                    ProjectsTable.id == project_id
                )
                .values(**update_data)
                .returning(ProjectsTable)
            )

            result = await session.execute(stmt)

            try:
                project_orm = result.scalar_one()
            except NoResultFound:
                raise NotFoundError(f"Project with id {project_id} not found")

            # Refresh to load relationships
            await session.refresh(project_orm, attribute_names=['memories'])

            # Convert to Pydantic model
            project = Project.model_validate(project_orm)

            logger.info(
                "Project updated",
                extra={"project_id": project_id, "project_name": project.name}
            )

            return project

    async def delete_project(
        self,
        user_id: UUID,
        project_id: int
    ) -> bool:
        """Delete project

        Removes project metadata. Linked entities (memories, code artifacts,
        documents) are preserved - only associations are removed (CASCADE).

        Args:
            user_id: User ID for RLS
            project_id: Project ID to delete

        Returns:
            True if project was deleted, False if not found
        """
        logger.info(
            "Deleting project",
            extra={"user_id": str(user_id), "project_id": project_id}
        )

        async with self.db_adapter.session(user_id) as session:
            stmt = delete(ProjectsTable).where(
                ProjectsTable.user_id == user_id,
                ProjectsTable.id == project_id
            )

            result = await session.execute(stmt)
            deleted = result.rowcount > 0

            if deleted:
                logger.info(
                    "Project deleted",
                    extra={"project_id": project_id, "user_id": str(user_id)}
                )
            else:
                logger.info(
                    "Project not found for deletion",
                    extra={"project_id": project_id, "user_id": str(user_id)}
                )

            return deleted
