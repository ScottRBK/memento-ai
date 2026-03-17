"""
SQLite repository for File data access operations
"""
import base64
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, or_, func

from app.repositories.sqlite.sqlite_tables import FilesTable
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.models.file_models import (
    File,
    FileCreate,
    FileUpdate,
    FileSummary
)
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class SqliteFileRepository:
    """Repository for File operations in SQLite"""

    def __init__(self, db_adapter: SqliteDatabaseAdapter):
        """Initialize with database adapter

        Args:
            db_adapter: SQLite database adapter for session management
        """
        self.db_adapter = db_adapter
        logger.info("SQLite file repository initialized")

    async def create_file(
        self,
        user_id: UUID,
        file_data: FileCreate
    ) -> File:
        """Create new file

        Args:
            user_id: User ID for ownership
            file_data: FileCreate with file details (data is base64)

        Returns:
            Created File with generated ID, size_bytes, and timestamps
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Decode base64 to bytes for storage
                decoded_data = base64.b64decode(file_data.data)
                size_bytes = len(decoded_data)

                file_table = FilesTable(
                    user_id=str(user_id),
                    filename=file_data.filename,
                    description=file_data.description,
                    data=decoded_data,
                    mime_type=file_data.mime_type,
                    size_bytes=size_bytes,
                    tags=file_data.tags,
                    project_id=file_data.project_id
                )

                session.add(file_table)
                await session.commit()
                await session.refresh(file_table)

                return self._to_file_model(file_table)

        except Exception as e:
            logger.error(
                "Failed to create file",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_file_by_id(
        self,
        user_id: UUID,
        file_id: int
    ) -> File | None:
        """Get file by ID with ownership check (includes base64 data)

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to retrieve

        Returns:
            File if found and owned by user, None otherwise
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(FilesTable).where(
                    FilesTable.id == file_id,
                    FilesTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                file_table = result.scalar_one_or_none()

                if not file_table:
                    return None

                return self._to_file_model(file_table)

        except Exception as e:
            logger.error(
                f"Failed to get file {file_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "file_id": file_id,
                    "error": str(e)
                }
            )
            raise

    async def list_files(
        self,
        user_id: UUID,
        project_id: int | None = None,
        mime_type: str | None = None,
        tags: List[str] | None = None
    ) -> List[FileSummary]:
        """List files with optional filtering (excludes binary data)

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            mime_type: Optional filter by MIME type
            tags: Optional filter by tags (returns files with ANY of these tags)

        Returns:
            List of FileSummary (lightweight, excludes base64 data)
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(FilesTable).where(
                    FilesTable.user_id == str(user_id)
                )

                if project_id is not None:
                    stmt = stmt.where(FilesTable.project_id == project_id)

                if mime_type:
                    stmt = stmt.where(FilesTable.mime_type == mime_type)

                if tags:
                    # SQLite JSON array search - finds files with ANY of the provided tags
                    tag_conditions = [
                        func.json_extract(FilesTable.tags, '$').like(f'%"{tag}"%')
                        for tag in tags
                    ]
                    stmt = stmt.where(or_(*tag_conditions))

                stmt = stmt.order_by(FilesTable.created_at.desc())

                result = await session.execute(stmt)
                files = result.scalars().all()

                return [FileSummary.model_validate(f) for f in files]

        except Exception as e:
            logger.error(
                "Failed to list files",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def update_file(
        self,
        user_id: UUID,
        file_id: int,
        file_data: FileUpdate
    ) -> File:
        """Update file (PATCH semantics)

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to update
            file_data: FileUpdate with fields to change

        Returns:
            Updated File

        Raises:
            NotFoundError: If file not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(FilesTable).where(
                    FilesTable.id == file_id,
                    FilesTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                file_table = result.scalar_one_or_none()

                if not file_table:
                    raise NotFoundError(f"File {file_id} not found")

                update_data = file_data.model_dump(exclude_unset=True)

                # Handle data field specially - decode base64 and update size
                if "data" in update_data and update_data["data"] is not None:
                    decoded_data = base64.b64decode(update_data["data"])
                    file_table.data = decoded_data
                    file_table.size_bytes = len(decoded_data)
                    del update_data["data"]

                for field, value in update_data.items():
                    setattr(file_table, field, value)

                file_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(file_table)

                return self._to_file_model(file_table)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update file {file_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "file_id": file_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_file(
        self,
        user_id: UUID,
        file_id: int
    ) -> bool:
        """Delete file (cascade removes associations)

        Args:
            user_id: User ID for ownership verification
            file_id: File ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(FilesTable).where(
                    FilesTable.id == file_id,
                    FilesTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                file_table = result.scalar_one_or_none()

                if not file_table:
                    return False

                await session.delete(file_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete file {file_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "file_id": file_id,
                    "error": str(e)
                }
            )
            raise

    @staticmethod
    def _to_file_model(file_table: FilesTable) -> File:
        """Convert ORM model to Pydantic model, encoding data as base64"""
        return File(
            id=file_table.id,
            filename=file_table.filename,
            description=file_table.description,
            data=base64.b64encode(file_table.data).decode("utf-8"),
            mime_type=file_table.mime_type,
            size_bytes=file_table.size_bytes,
            tags=file_table.tags,
            project_id=file_table.project_id,
            created_at=file_table.created_at,
            updated_at=file_table.updated_at,
        )
