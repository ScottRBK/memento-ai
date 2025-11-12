"""
Document Service - Business logic for document operations

This service implements functionality for managing documents:
    - CRUD operations (create, read, update, delete)
    - Filtering and search
    - Project association
    - Memory linking (via memory service)
"""
from typing import List
from uuid import UUID

from app.config.logging_config import logging
from app.protocols.document_protocol import DocumentRepository
from app.models.document_models import (
    Document,
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary
)
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class DocumentService:
    """Service layer for document operations

    Handles business logic for creating, updating, querying, and deleting documents.
    Uses repository protocol for data access.
    """

    def __init__(self, document_repo: DocumentRepository):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            document_repo: Document repository implementing the protocol
        """
        self.document_repo = document_repo
        logger.info("Document service initialized")

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
        else:
            logger.warning(
                "document not found for deletion",
                extra={
                    "document_id": document_id,
                    "user_id": str(user_id)
                }
            )

        return success
