"""
Document Service - Business logic for document operations

This service implements functionality for managing documents:
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
from app.protocols.document_protocol import DocumentRepository
from app.models.document_models import (
    Document,
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary
)
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class DocumentService:
    """Service layer for document operations

    Handles business logic for creating, updating, querying, and deleting documents.
    Uses repository protocol for data access.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            document_repo: Document repository implementing the protocol
            event_bus: Optional event bus for activity tracking
        """
        self.document_repo = document_repo
        self._event_bus = event_bus
        logger.info("Document service initialized")

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
            entity_type: Type of entity (document)
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

    async def create_document(
        self,
        user_id: UUID,
        document_data: DocumentCreate
    ) -> Document:
        """Create new document

        Args:
            user_id: User ID for ownership
            document_data: DocumentCreate with title, description, content, etc.

        Returns:
            Created Document with generated ID and timestamps
        """
        logger.info(
            "creating document",
            extra={
                "title": document_data.title[:50],
                "document_type": document_data.document_type,
                "user_id": str(user_id)
            }
        )

        document = await self.document_repo.create_document(
            user_id=user_id,
            document_data=document_data
        )

        logger.info(
            "document created",
            extra={
                "document_id": document.id,
                "user_id": str(user_id)
            }
        )

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.DOCUMENT,
            entity_id=document.id,
            action=ActionType.CREATED,
            snapshot=document.model_dump(mode="json"),
        )

        return document

    async def get_document(
        self,
        user_id: UUID,
        document_id: int
    ) -> Document:
        """Get document by ID with ownership verification

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to retrieve

        Returns:
            Document with full details

        Raises:
            NotFoundError: If document not found or not owned by user
        """
        logger.info(
            "getting document",
            extra={
                "document_id": document_id,
                "user_id": str(user_id)
            }
        )

        document = await self.document_repo.get_document_by_id(
            user_id=user_id,
            document_id=document_id
        )

        if not document:
            raise NotFoundError(f"Document {document_id} not found")

        logger.info(
            "document retrieved",
            extra={
                "document_id": document_id,
                "user_id": str(user_id)
            }
        )

        # Emit read event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.DOCUMENT,
                entity_id=document_id,
                action=ActionType.READ,
                snapshot=document.model_dump(mode="json"),
            )

        return document

    async def list_documents(
        self,
        user_id: UUID,
        project_id: int | None = None,
        document_type: str | None = None,
        tags: List[str] | None = None
    ) -> List[DocumentSummary]:
        """List documents with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            document_type: Optional filter by document type
            tags: Optional filter by tags (returns documents with ANY of these tags)

        Returns:
            List of DocumentSummary (lightweight, excludes full content)
        """
        logger.info(
            "listing documents",
            extra={
                "user_id": str(user_id),
                "project_id": project_id,
                "document_type": document_type,
                "tags": tags
            }
        )

        documents = await self.document_repo.list_documents(
            user_id=user_id,
            project_id=project_id,
            document_type=document_type,
            tags=tags
        )

        logger.info(
            "documents retrieved",
            extra={
                "count": len(documents),
                "user_id": str(user_id)
            }
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.DOCUMENT,
                entity_id=0,  # Query spans multiple documents
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [d.id for d in documents],
                    "total_count": len(documents),
                },
                metadata={
                    "project_id": project_id,
                    "document_type": document_type,
                    "tags": tags,
                },
            )

        return documents

    async def update_document(
        self,
        user_id: UUID,
        document_id: int,
        document_data: DocumentUpdate
    ) -> Document:
        """Update existing document (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to update
            document_data: DocumentUpdate with fields to change

        Returns:
            Updated Document

        Raises:
            NotFoundError: If document not found or not owned by user
        """
        logger.info(
            "updating document",
            extra={
                "document_id": document_id,
                "user_id": str(user_id)
            }
        )

        # Get existing document for change detection
        existing_document = await self.document_repo.get_document_by_id(
            user_id=user_id,
            document_id=document_id
        )

        if not existing_document:
            raise NotFoundError(f"Document {document_id} not found")

        # Detect changes
        changed_fields = get_changed_fields(
            input_model=document_data, existing_model=existing_document
        )

        document = await self.document_repo.update_document(
            user_id=user_id,
            document_id=document_id,
            document_data=document_data
        )

        logger.info(
            "document updated",
            extra={
                "document_id": document_id,
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
                entity_type=EntityType.DOCUMENT,
                entity_id=document_id,
                action=ActionType.UPDATED,
                snapshot=document.model_dump(mode="json"),
                changes=changes_dict,
            )

        return document

    async def delete_document(
        self,
        user_id: UUID,
        document_id: int
    ) -> bool:
        """Delete document (cascade removes memory associations)

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting document",
            extra={
                "document_id": document_id,
                "user_id": str(user_id)
            }
        )

        # Fetch document before deletion for snapshot
        existing_document = await self.document_repo.get_document_by_id(
            user_id=user_id,
            document_id=document_id
        )

        success = await self.document_repo.delete_document(
            user_id=user_id,
            document_id=document_id
        )

        if success:
            logger.info(
                "document deleted",
                extra={
                    "document_id": document_id,
                    "user_id": str(user_id)
                }
            )

            # Emit deleted event with pre-deletion snapshot
            if existing_document:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.DOCUMENT,
                    entity_id=document_id,
                    action=ActionType.DELETED,
                    snapshot=existing_document.model_dump(mode="json"),
                )
        else:
            logger.warning(
                "document not found for deletion",
                extra={
                    "document_id": document_id,
                    "user_id": str(user_id)
                }
            )

        return success
