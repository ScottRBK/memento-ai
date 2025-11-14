"""
SQLite repository for Document data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, or_, func

from app.repositories.sqlite.sqlite_tables import DocumentsTable
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.models.document_models import (
    Document,
    DocumentCreate,
    DocumentUpdate,
    DocumentSummary
)
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class SqliteDocumentRepository:
    """Repository for Document operations in SQLite"""

    def __init__(self, db_adapter: SqliteDatabaseAdapter):
        """Initialize with database adapter

        Args:
            db_adapter: SQLite database adapter for session management
        """
        self.db_adapter = db_adapter
        logger.info("SQLite document repository initialized")

    async def create_document(
        self,
        user_id: UUID,
        document_data: DocumentCreate
    ) -> Document:
        """Create new document

        Args:
            user_id: User ID for ownership
            document_data: DocumentCreate with document details

        Returns:
            Created Document with generated ID and timestamps
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Calculate size_bytes from content if not provided
                size_bytes = document_data.size_bytes
                if size_bytes is None:
                    size_bytes = len(document_data.content.encode('utf-8'))

                # Create ORM model from Pydantic
                document_table = DocumentsTable(
                    user_id=str(user_id),
                    title=document_data.title,
                    description=document_data.description,
                    content=document_data.content,
                    document_type=document_data.document_type,
                    filename=document_data.filename,
                    size_bytes=size_bytes,
                    tags=document_data.tags,
                    project_id=document_data.project_id
                )

                session.add(document_table)
                await session.commit()
                await session.refresh(document_table)

                # Convert ORM to Pydantic
                return Document.model_validate(document_table)

        except Exception as e:
            logger.error(
                "Failed to create document",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_document_by_id(
        self,
        user_id: UUID,
        document_id: int
    ) -> Document | None:
        """Get document by ID with ownership check

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to retrieve

        Returns:
            Document if found and owned by user, None otherwise
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Query with ownership check
                stmt = select(DocumentsTable).where(
                    DocumentsTable.id == document_id,
                    DocumentsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                document_table = result.scalar_one_or_none()

                if not document_table:
                    return None

                return Document.model_validate(document_table)

        except Exception as e:
            logger.error(
                f"Failed to get document {document_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "document_id": document_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Build query with filters
                stmt = select(DocumentsTable).where(
                    DocumentsTable.user_id == str(user_id)
                )

                if project_id is not None:
                    stmt = stmt.where(DocumentsTable.project_id == project_id)

                if document_type:
                    stmt = stmt.where(DocumentsTable.document_type == document_type)

                if tags:
                    # SQLite JSON array search - finds documents with ANY of the provided tags
                    tag_conditions = [
                        func.json_extract(DocumentsTable.tags, '$').like(f'%"{tag}"%')
                        for tag in tags
                    ]
                    stmt = stmt.where(or_(*tag_conditions))

                # Order by creation date (newest first)
                stmt = stmt.order_by(DocumentsTable.created_at.desc())

                result = await session.execute(stmt)
                documents = result.scalars().all()

                return [DocumentSummary.model_validate(d) for d in documents]

        except Exception as e:
            logger.error(
                "Failed to list documents",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def update_document(
        self,
        user_id: UUID,
        document_id: int,
        document_data: DocumentUpdate
    ) -> Document:
        """Update document (PATCH semantics)

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Fetch existing document
                stmt = select(DocumentsTable).where(
                    DocumentsTable.id == document_id,
                    DocumentsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                document_table = result.scalar_one_or_none()

                if not document_table:
                    raise NotFoundError(f"Document {document_id} not found")

                # Update only provided fields (PATCH)
                update_data = document_data.model_dump(exclude_unset=True)

                # Recalculate size_bytes if content is being updated
                if "content" in update_data and update_data["content"]:
                    update_data["size_bytes"] = len(update_data["content"].encode('utf-8'))

                for field, value in update_data.items():
                    setattr(document_table, field, value)

                # Update timestamp
                document_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(document_table)

                return Document.model_validate(document_table)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update document {document_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "document_id": document_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_document(
        self,
        user_id: UUID,
        document_id: int
    ) -> bool:
        """Delete document (cascade removes associations)

        Args:
            user_id: User ID for ownership verification
            document_id: Document ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Check ownership and get document
                stmt = select(DocumentsTable).where(
                    DocumentsTable.id == document_id,
                    DocumentsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                document_table = result.scalar_one_or_none()

                if not document_table:
                    return False

                await session.delete(document_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete document {document_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "document_id": document_id,
                    "error": str(e)
                }
            )
            raise
