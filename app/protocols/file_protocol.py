"""Protocol (interface) for File Repository

Defines the contract for file data access operations.
Concrete implementations must provide all methods defined here.
"""
from typing import Protocol
from uuid import UUID

from app.models.file_models import (
    File,
    FileCreate,
    FileSummary,
    FileUpdate,
)


class FileRepository(Protocol):
    """Contract for File Repository operations

    All repository implementations must provide these methods.
    Services depend on this protocol, not concrete implementations.
    """

    async def create_file(
        self,
        user_id: UUID,
        file_data: FileCreate,
    ) -> File:
        """Create a new file

        Args:
            user_id: User ID for ownership
            file_data: FileCreate with filename, description, data (base64), mime_type, tags

        Returns:
            Created File with generated ID, size_bytes, and timestamps

        Raises:
            ValidationError: If file_data is invalid
        """
        ...

    async def get_file_by_id(
        self,
        user_id: UUID,
        file_id: int,
    ) -> File | None:
        """Get a single file by ID (includes base64 data)

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to retrieve

        Returns:
            File if found and owned by user, None otherwise
        """
        ...

    async def list_files(
        self,
        user_id: UUID,
        project_id: int | None = None,
        mime_type: str | None = None,
        tags: list[str] | None = None,
    ) -> list[FileSummary]:
        """List files with optional filtering (excludes binary data)

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            mime_type: Optional filter by MIME type
            tags: Optional filter by tags (returns files with ANY of these tags)

        Returns:
            List of FileSummary (lightweight, excludes base64 data)
            Sorted by creation date (newest first)
        """
        ...

    async def update_file(
        self,
        user_id: UUID,
        file_id: int,
        file_data: FileUpdate,
    ) -> File:
        """Update an existing file (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to update
            file_data: FileUpdate with fields to change

        Returns:
            Updated File

        Raises:
            NotFoundError: If file not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_file(
        self,
        user_id: UUID,
        file_id: int,
    ) -> bool:
        """Delete a file

        Cascade removes memory/entity associations. Memories/entities are preserved.

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...
