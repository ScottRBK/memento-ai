from typing import TYPE_CHECKING, List
from uuid import UUID

from app.config.logging_config import logging
from app.config.settings import settings
from app.models.activity_models import (
    ActivityEvent,
    ActorType,
    ActionType,
    EntityType,
)
from app.models.project_models import (
    Project,
    ProjectCreate,
    ProjectStatus,
    ProjectSummary,
    ProjectUpdate,
)
from app.protocols.project_protocol import ProjectRepository
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class ProjectService:
    """Service layer for project operations

    Orchestrates business logic for project management including creation,
    updates, filtering, and lifecycle management. Projects organize memories,
    code artifacts, and documents by context.

    This service is simpler than MemoryService - primarily CRUD operations
    with filtering. No embeddings, auto-linking, or token budget management.
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize project service with repository

        Args:
            project_repo: Project repository implementation (protocol-based)
            event_bus: Optional event bus for activity tracking
        """
        self.project_repo = project_repo
        self._event_bus = event_bus
        logger.info("Project service initialised")

    async def _emit_event(
        self,
        user_id: UUID,
        entity_type: EntityType,
        entity_id: int,
        action: ActionType,
        snapshot: dict,
        changes: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Emit an activity event to the event bus.

        This is a no-op if no event bus is configured.

        Args:
            user_id: User ID for the event
            entity_type: Type of entity (project)
            entity_id: ID of the entity
            action: Action that occurred (created, updated, deleted, etc.)
            snapshot: Full entity state at event time
            changes: Field changes for updates
            metadata: Additional context
        """
        if self._event_bus is None:
            return

        event = ActivityEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            snapshot=snapshot,
            actor=ActorType.USER,
            metadata=metadata,
            user_id=str(user_id),
        )

        await self._event_bus.emit(event)

    async def list_projects(
        self,
        user_id: UUID,
        status: ProjectStatus | None = None,
        repo_name: str | None = None,
        name: str | None = None,
    ) -> List[ProjectSummary]:
        """List projects with optional filtering

        Retrieves lightweight project summaries (excludes description/notes
        to save tokens). Supports filtering by status, repository name, and
        project name.

        Args:
            user_id: User ID for RLS (row-level security)
            status: Optional filter by project status (active/archived/completed)
            repo_name: Optional filter by repository name (e.g., 'owner/repo')
            name: Optional filter by project name (case-insensitive partial match)

        Returns:
            List of ProjectSummary objects matching filters, ordered by created_at desc
        """
        logger.info(
            "listing projects",
            extra={
                "user_id": str(user_id),
                "status": status.value if status else None,
                "repo_name": repo_name,
                "name": name,
            },
        )

        projects = await self.project_repo.list_projects(
            user_id=user_id, status=status, repo_name=repo_name, name=name
        )

        logger.info(
            "projects retrieved",
            extra={"count": len(projects), "user_id": str(user_id)},
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.PROJECT,
                entity_id=0,  # Query spans multiple projects
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [p.id for p in projects],
                    "total_count": len(projects),
                },
                metadata={
                    "status": status.value if status else None,
                    "repo_name": repo_name,
                    "name": name,
                },
            )

        return projects

    async def get_project(self, user_id: UUID, project_id: int) -> Project | None:
        """Get single project by ID

        Retrieves complete project details including description, notes,
        and relationship counts.

        Args:
            user_id: User ID for RLS
            project_id: Project ID to retrieve

        Returns:
            Project if found, None otherwise
        """
        logger.info(
            "getting project", extra={"user_id": str(user_id), "project_id": project_id}
        )

        project = await self.project_repo.get_project_by_id(
            user_id=user_id, project_id=project_id
        )

        if project:
            logger.info(
                "project retrieved",
                extra={"project_id": project_id, "project_name": project.name},
            )

            # Emit read event (opt-in via ACTIVITY_TRACK_READS)
            if settings.ACTIVITY_TRACK_READS and self._event_bus:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.PROJECT,
                    entity_id=project_id,
                    action=ActionType.READ,
                    snapshot=project.model_dump(mode="json"),
                )
        else:
            logger.info(
                "project not found",
                extra={"project_id": project_id, "user_id": str(user_id)},
            )

        return project

    async def create_project(
        self, user_id: UUID, project_data: ProjectCreate
    ) -> Project:
        """Create new project

        Creates project with provided metadata. Status defaults to 'active'
        if not specified. Generated fields (id, timestamps) added by repository.

        Args:
            user_id: User ID for RLS
            project_data: Project creation data (name, description, type required)

        Returns:
            Created Project with generated ID and timestamps

        Raises:
            ValidationError: If project_data validation fails
        """
        logger.info(
            "creating project",
            extra={
                "user_id": str(user_id),
                "project_name": project_data.name,
                "type": project_data.project_type.value,
            },
        )

        project = await self.project_repo.create_project(
            user_id=user_id, project_data=project_data
        )

        logger.info(
            "project created",
            extra={
                "project_id": project.id,
                "project_name": project.name,
                "user_id": str(user_id),
            },
        )

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.PROJECT,
            entity_id=project.id,
            action=ActionType.CREATED,
            snapshot=project.model_dump(mode="json"),
        )

        return project

    async def update_project(
        self, user_id: UUID, project_id: int, project_data: ProjectUpdate
    ) -> Project | None:
        """Update existing project

        Updates project fields using PATCH semantics (only provided fields updated).
        Includes pre-flight validation and change detection to avoid unnecessary
        database operations.

        Args:
            user_id: User ID for RLS
            project_id: Project ID to update
            project_data: Project update data (all fields optional)

        Returns:
            Updated Project if found and updated, None if not found

        Raises:
            ValidationError: If project_data validation fails
        """
        logger.info(
            "updating project",
            extra={"user_id": str(user_id), "project_id": project_id},
        )

        # Pre-flight validation: get existing project
        existing_project = await self.project_repo.get_project_by_id(
            user_id=user_id, project_id=project_id
        )

        if not existing_project:
            logger.info(
                "project not found for update",
                extra={"project_id": project_id, "user_id": str(user_id)},
            )
            return None

        # Business logic: detect actual changes
        changed_fields = get_changed_fields(
            input_model=project_data, existing_model=existing_project
        )

        if not changed_fields:
            logger.info(
                "no changes detected, returning existing project",
                extra={"project_id": project_id},
            )
            return existing_project

        logger.info(
            "changes detected",
            extra={
                "project_id": project_id,
                "changed_fields": list(changed_fields.keys()),
            },
        )

        # Update project in repository
        updated_project = await self.project_repo.update_project(
            user_id=user_id, project_id=project_id, project_data=project_data
        )

        logger.info(
            "project updated",
            extra={"project_id": project_id, "project_name": updated_project.name},
        )

        # Emit updated event with changes
        changes_dict = {
            field: {"old": old, "new": new}
            for field, (old, new) in changed_fields.items()
        }
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.PROJECT,
            entity_id=project_id,
            action=ActionType.UPDATED,
            snapshot=updated_project.model_dump(mode="json"),
            changes=changes_dict,
        )

        return updated_project

    async def delete_project(self, user_id: UUID, project_id: int) -> bool:
        """Delete project

        Removes project metadata. Linked entities (memories, code artifacts,
        documents) are preserved - only associations are removed.

        Args:
            user_id: User ID for RLS
            project_id: Project ID to delete

        Returns:
            True if project was deleted, False if not found

        Note:
            Deletion is permanent and cannot be undone. Consider archiving
            (status=archived) instead for soft delete behavior.
        """
        logger.info(
            "deleting project",
            extra={"user_id": str(user_id), "project_id": project_id},
        )

        # Pre-flight validation: verify project exists
        existing_project = await self.project_repo.get_project_by_id(
            user_id=user_id, project_id=project_id
        )

        if not existing_project:
            logger.info(
                "project not found for deletion",
                extra={"project_id": project_id, "user_id": str(user_id)},
            )
            return False

        # Delete project
        success = await self.project_repo.delete_project(
            user_id=user_id, project_id=project_id
        )

        if success:
            logger.info(
                "project deleted",
                extra={
                    "project_id": project_id,
                    "project_name": existing_project.name,
                    "user_id": str(user_id),
                },
            )

            # Emit deleted event with pre-deletion snapshot
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.PROJECT,
                entity_id=project_id,
                action=ActionType.DELETED,
                snapshot=existing_project.model_dump(mode="json"),
            )
        else:
            logger.warning(
                "project deletion failed",
                extra={"project_id": project_id, "user_id": str(user_id)},
            )

        return success
