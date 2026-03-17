"""
File Service - Business logic for file operations

This service implements functionality for managing binary files:
    - CRUD operations (create, read, update, delete)
    - Filtering and search
    - Project association
    - Memory/entity linking (via association tables)
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
from app.protocols.file_protocol import FileRepository
from app.models.file_models import (
    File,
    FileCreate,
    FileUpdate,
    FileSummary
)
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class FileService:
    """Service layer for file operations

    Handles business logic for creating, updating, querying, and deleting files.
    Uses repository protocol for data access.
    """

    def __init__(
        self,
        file_repo: FileRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            file_repo: File repository implementing the protocol
            event_bus: Optional event bus for activity tracking
        """
        self.file_repo = file_repo
        self._event_bus = event_bus
        logger.info("File service initialized")

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
        """Emit an activity event to the event bus.

        This is a no-op if no event bus is configured.
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

    def _snapshot_without_data(self, file: File) -> dict:
        """Create a snapshot dict excluding the base64 data field to avoid bloating events."""
        snapshot = file.model_dump(mode="json")
        snapshot.pop("data", None)
        return snapshot

    async def create_file(
        self,
        user_id: UUID,
        file_data: FileCreate
    ) -> File:
        """Create new file

        Args:
            user_id: User ID for ownership
            file_data: FileCreate with filename, description, data (base64), mime_type, tags

        Returns:
            Created File with generated ID, size_bytes, and timestamps
        """
        logger.info(
            "creating file",
            extra={
                "filename": file_data.filename[:50],
                "mime_type": file_data.mime_type,
                "user_id": str(user_id)
            }
        )

        file = await self.file_repo.create_file(
            user_id=user_id,
            file_data=file_data
        )

        logger.info(
            "file created",
            extra={
                "file_id": file.id,
                "user_id": str(user_id)
            }
        )

        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.FILE,
            entity_id=file.id,
            action=ActionType.CREATED,
            snapshot=self._snapshot_without_data(file),
        )

        return file

    async def get_file(
        self,
        user_id: UUID,
        file_id: int
    ) -> File:
        """Get file by ID with ownership verification

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to retrieve

        Returns:
            File with full details including base64 data

        Raises:
            NotFoundError: If file not found or not owned by user
        """
        logger.info(
            "getting file",
            extra={
                "file_id": file_id,
                "user_id": str(user_id)
            }
        )

        file = await self.file_repo.get_file_by_id(
            user_id=user_id,
            file_id=file_id
        )

        if not file:
            raise NotFoundError(f"File {file_id} not found")

        logger.info(
            "file retrieved",
            extra={
                "file_id": file_id,
                "user_id": str(user_id)
            }
        )

        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.FILE,
                entity_id=file_id,
                action=ActionType.READ,
                snapshot=self._snapshot_without_data(file),
            )

        return file

    async def list_files(
        self,
        user_id: UUID,
        project_id: int | None = None,
        mime_type: str | None = None,
        tags: List[str] | None = None
    ) -> List[FileSummary]:
        """List files with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            mime_type: Optional filter by MIME type
            tags: Optional filter by tags (returns files with ANY of these tags)

        Returns:
            List of FileSummary (lightweight, excludes base64 data)
        """
        logger.info(
            "listing files",
            extra={
                "user_id": str(user_id),
                "project_id": project_id,
                "mime_type": mime_type,
                "tags": tags
            }
        )

        files = await self.file_repo.list_files(
            user_id=user_id,
            project_id=project_id,
            mime_type=mime_type,
            tags=tags
        )

        logger.info(
            "files retrieved",
            extra={
                "count": len(files),
                "user_id": str(user_id)
            }
        )

        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.FILE,
                entity_id=0,
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [f.id for f in files],
                    "total_count": len(files),
                },
                metadata={
                    "project_id": project_id,
                    "mime_type": mime_type,
                    "tags": tags,
                },
            )

        return files

    async def update_file(
        self,
        user_id: UUID,
        file_id: int,
        file_data: FileUpdate
    ) -> File:
        """Update existing file (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to update
            file_data: FileUpdate with fields to change

        Returns:
            Updated File

        Raises:
            NotFoundError: If file not found or not owned by user
        """
        logger.info(
            "updating file",
            extra={
                "file_id": file_id,
                "user_id": str(user_id)
            }
        )

        existing_file = await self.file_repo.get_file_by_id(
            user_id=user_id,
            file_id=file_id
        )

        if not existing_file:
            raise NotFoundError(f"File {file_id} not found")

        changed_fields = get_changed_fields(
            input_model=file_data, existing_model=existing_file
        )

        file = await self.file_repo.update_file(
            user_id=user_id,
            file_id=file_id,
            file_data=file_data
        )

        logger.info(
            "file updated",
            extra={
                "file_id": file_id,
                "user_id": str(user_id)
            }
        )

        if changed_fields:
            # Exclude 'data' from changes to avoid bloating events
            changes_dict = {
                field: {"old": old, "new": new}
                for field, (old, new) in changed_fields.items()
                if field != "data"
            }
            if changes_dict:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.FILE,
                    entity_id=file_id,
                    action=ActionType.UPDATED,
                    snapshot=self._snapshot_without_data(file),
                    changes=changes_dict,
                )

        return file

    async def delete_file(
        self,
        user_id: UUID,
        file_id: int
    ) -> bool:
        """Delete file (cascade removes memory/entity associations)

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting file",
            extra={
                "file_id": file_id,
                "user_id": str(user_id)
            }
        )

        existing_file = await self.file_repo.get_file_by_id(
            user_id=user_id,
            file_id=file_id
        )

        success = await self.file_repo.delete_file(
            user_id=user_id,
            file_id=file_id
        )

        if success:
            logger.info(
                "file deleted",
                extra={
                    "file_id": file_id,
                    "user_id": str(user_id)
                }
            )

            if existing_file:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.FILE,
                    entity_id=file_id,
                    action=ActionType.DELETED,
                    snapshot=self._snapshot_without_data(existing_file),
                )
        else:
            logger.warning(
                "file not found for deletion",
                extra={
                    "file_id": file_id,
                    "user_id": str(user_id)
                }
            )

        return success
