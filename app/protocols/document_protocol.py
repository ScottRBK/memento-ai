"""
Protocol (interface) for Document Repository

Defines the contract for document data access operations.
Concrete implementations must provide all methods defined here.
"""
from typing import Protocol, List
from uuid import UUID

from app.models.document_models import (
    Document,
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary
)


class DocumentRepository(Protocol):
    """Contract for Document Repository operations

    All repository implementations must provide these methods.
    Services depend on this protocol, not concrete implementations.
    """

    async def create_document(
        self,
        user_id: UUID,
        document_data: DocumentCreate
    ) -> Document:
        """Create a new document

        Args:
            user_id: User ID for ownership
            document_data: DocumentCreate with title, description, content, etc.

        Returns:
            Created Document with generated ID and timestamps

        Raises:
            ValidationError: If document_data is invalid
        """
        ...

    async def get_document_by_id(
        self,
        user_id: UUID,
        document_id: int
    ) -> Document | None:
        """Get a single document by ID

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to retrieve

        Returns:
            Document if found and owned by user, None otherwise
        """
        ...

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
            document_type: Optional filter by document type (e.g., 'markdown', 'text')
            tags: Optional filter by tags (returns documents with ANY of these tags)

        Returns:
            List of DocumentSummary (lightweight, excludes full content)
            Sorted by creation date (newest first)
        """
        ...

    async def update_document(
        self,
        user_id: UUID,
        document_id: int,
        document_data: DocumentUpdate
    ) -> Document:
        """Update an existing document (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to update
            document_data: DocumentUpdate with fields to change

        Returns:
            Updated Document

        Raises:
            NotFoundError: If document not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_document(
        self,
        user_id: UUID,
        document_id: int
    ) -> bool:
        """Delete a document

        Cascade removes memory associations. Memories are preserved.

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...
