"""
Code Artifact Service - Business logic for code artifact operations

This service implements functionality for managing code artifacts:
    - CRUD operations (create, read, update, delete)
    - Filtering and search
    - Project association
    - Memory linking (via memory service)
"""
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
from app.protocols.code_artifact_protocol import CodeArtifactRepository
from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate,
    CodeArtifactSummary
)
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class CodeArtifactService:
    """Service layer for code artifact operations

    Handles business logic for creating, updating, querying, and deleting code artifacts.
    Uses repository protocol for data access.
    """

    def __init__(
        self,
        artifact_repo: CodeArtifactRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            artifact_repo: Code artifact repository implementing the protocol
            event_bus: Optional event bus for activity tracking
        """
        self.artifact_repo = artifact_repo
        self._event_bus = event_bus
        logger.info("Code artifact service initialized")

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
            entity_type: Type of entity (code_artifact)
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

    async def create_code_artifact(
        self,
        user_id: UUID,
        artifact_data: CodeArtifactCreate
    ) -> CodeArtifact:
        """Create new code artifact

        Args:
            user_id: User ID for ownership
            artifact_data: CodeArtifactCreate with title, description, code, language, tags

        Returns:
            Created CodeArtifact with generated ID and timestamps
        """
        logger.info(
            "creating code artifact",
            extra={
                "title": artifact_data.title[:50],
                "language": artifact_data.language,
                "user_id": str(user_id)
            }
        )

        artifact = await self.artifact_repo.create_code_artifact(
            user_id=user_id,
            artifact_data=artifact_data
        )

        logger.info(
            "code artifact created",
            extra={
                "artifact_id": artifact.id,
                "user_id": str(user_id)
            }
        )

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.CODE_ARTIFACT,
            entity_id=artifact.id,
            action=ActionType.CREATED,
            snapshot=artifact.model_dump(mode="json"),
        )

        return artifact

    async def get_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> CodeArtifact:
        """Get artifact by ID with ownership verification

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to retrieve

        Returns:
            CodeArtifact with full details

        Raises:
            NotFoundError: If artifact not found or not owned by user
        """
        logger.info(
            "getting code artifact",
            extra={
                "artifact_id": artifact_id,
                "user_id": str(user_id)
            }
        )

        artifact = await self.artifact_repo.get_code_artifact_by_id(
            user_id=user_id,
            artifact_id=artifact_id
        )

        if not artifact:
            raise NotFoundError(f"Code artifact {artifact_id} not found")

        logger.info(
            "code artifact retrieved",
            extra={
                "artifact_id": artifact_id,
                "user_id": str(user_id)
            }
        )

        # Emit read event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.CODE_ARTIFACT,
                entity_id=artifact_id,
                action=ActionType.READ,
                snapshot=artifact.model_dump(mode="json"),
            )

        return artifact

    async def list_code_artifacts(
        self,
        user_id: UUID,
        project_id: int | None = None,
        language: str | None = None,
        tags: List[str] | None = None
    ) -> List[CodeArtifactSummary]:
        """List artifacts with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            language: Optional filter by programming language
            tags: Optional filter by tags (returns artifacts with ANY of these tags)

        Returns:
            List of CodeArtifactSummary (lightweight, excludes full code)
        """
        logger.info(
            "listing code artifacts",
            extra={
                "user_id": str(user_id),
                "project_id": project_id,
                "language": language,
                "tags": tags
            }
        )

        artifacts = await self.artifact_repo.list_code_artifacts(
            user_id=user_id,
            project_id=project_id,
            language=language,
            tags=tags
        )

        logger.info(
            "code artifacts retrieved",
            extra={
                "count": len(artifacts),
                "user_id": str(user_id)
            }
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.CODE_ARTIFACT,
                entity_id=0,  # Query spans multiple artifacts
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [a.id for a in artifacts],
                    "total_count": len(artifacts),
                },
                metadata={
                    "project_id": project_id,
                    "language": language,
                    "tags": tags,
                },
            )

        return artifacts

    async def update_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int,
        artifact_data: CodeArtifactUpdate
    ) -> CodeArtifact:
        """Update existing artifact (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to update
            artifact_data: CodeArtifactUpdate with fields to change

        Returns:
            Updated CodeArtifact

        Raises:
            NotFoundError: If artifact not found or not owned by user
        """
        logger.info(
            "updating code artifact",
            extra={
                "artifact_id": artifact_id,
                "user_id": str(user_id)
            }
        )

        # Get existing artifact for change detection
        existing_artifact = await self.artifact_repo.get_code_artifact_by_id(
            user_id=user_id,
            artifact_id=artifact_id
        )

        if not existing_artifact:
            raise NotFoundError(f"Code artifact {artifact_id} not found")

        # Detect changes
        changed_fields = get_changed_fields(
            input_model=artifact_data, existing_model=existing_artifact
        )

        artifact = await self.artifact_repo.update_code_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
            artifact_data=artifact_data
        )

        logger.info(
            "code artifact updated",
            extra={
                "artifact_id": artifact_id,
                "user_id": str(user_id)
            }
        )

        # Emit updated event with changes
        if changed_fields:
            changes_dict = {
                field: {"old": old, "new": new}
                for field, (old, new) in changed_fields.items()
            }
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.CODE_ARTIFACT,
                entity_id=artifact_id,
                action=ActionType.UPDATED,
                snapshot=artifact.model_dump(mode="json"),
                changes=changes_dict,
            )

        return artifact

    async def delete_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> bool:
        """Delete artifact (cascade removes memory associations)

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting code artifact",
            extra={
                "artifact_id": artifact_id,
                "user_id": str(user_id)
            }
        )

        # Fetch artifact before deletion for snapshot
        existing_artifact = await self.artifact_repo.get_code_artifact_by_id(
            user_id=user_id,
            artifact_id=artifact_id
        )

        success = await self.artifact_repo.delete_code_artifact(
            user_id=user_id,
            artifact_id=artifact_id
        )

        if success:
            logger.info(
                "code artifact deleted",
                extra={
                    "artifact_id": artifact_id,
                    "user_id": str(user_id)
                }
            )

            # Emit deleted event with pre-deletion snapshot
            if existing_artifact:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.CODE_ARTIFACT,
                    entity_id=artifact_id,
                    action=ActionType.DELETED,
                    snapshot=existing_artifact.model_dump(mode="json"),
                )
        else:
            logger.warning(
                "code artifact not found for deletion",
                extra={
                    "artifact_id": artifact_id,
                    "user_id": str(user_id)
                }
            )

        return success
