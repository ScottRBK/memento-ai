"""
SQLite repository for Code Artifact data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, or_, func

from app.repositories.sqlite.sqlite_tables import CodeArtifactsTable
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate,
    CodeArtifactSummary
)
from app.exceptions import NotFoundError
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class SqliteCodeArtifactRepository:
    """Repository for Code Artifact operations in SQLite"""

    def __init__(self, db_adapter: SqliteDatabaseAdapter):
        """Initialize with database adapter

        Args:
            db_adapter: SQLite database adapter for session management
        """
        self.db_adapter = db_adapter
        logger.info("SQLite code artifact repository initialized")

    async def create_code_artifact(
        self,
        user_id: UUID,
        artifact_data: CodeArtifactCreate
    ) -> CodeArtifact:
        """Create new code artifact

        Args:
            user_id: User ID for ownership
            artifact_data: CodeArtifactCreate with artifact details

        Returns:
            Created CodeArtifact with generated ID and timestamps
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Create ORM model from Pydantic
                artifact_table = CodeArtifactsTable(
                    user_id=str(user_id),
                    title=artifact_data.title,
                    description=artifact_data.description,
                    code=artifact_data.code,
                    language=artifact_data.language.lower(),  # Ensure lowercase
                    tags=artifact_data.tags,
                    project_id=artifact_data.project_id
                )

                session.add(artifact_table)
                await session.commit()
                await session.refresh(artifact_table)

                # Convert ORM to Pydantic
                return CodeArtifact.model_validate(artifact_table)

        except Exception as e:
            logger.error(
                "Failed to create code artifact",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_code_artifact_by_id(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> CodeArtifact | None:
        """Get artifact by ID with ownership check

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to retrieve

        Returns:
            CodeArtifact if found and owned by user, None otherwise
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Query with ownership check
                stmt = select(CodeArtifactsTable).where(
                    CodeArtifactsTable.id == artifact_id,
                    CodeArtifactsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                artifact_table = result.scalar_one_or_none()

                if not artifact_table:
                    return None

                return CodeArtifact.model_validate(artifact_table)

        except Exception as e:
            logger.error(
                f"Failed to get code artifact {artifact_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "artifact_id": artifact_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Build query with filters
                stmt = select(CodeArtifactsTable).where(
                    CodeArtifactsTable.user_id == str(user_id)
                )

                if project_id is not None:
                    stmt = stmt.where(CodeArtifactsTable.project_id == project_id)

                if language:
                    # Case-insensitive language match (stored as lowercase)
                    stmt = stmt.where(CodeArtifactsTable.language == language.lower())

                if tags:
                    # SQLite JSON array search - finds artifacts with ANY of the provided tags
                    tag_conditions = [
                        func.json_extract(CodeArtifactsTable.tags, '$').like(f'%"{tag}"%')
                        for tag in tags
                    ]
                    stmt = stmt.where(or_(*tag_conditions))

                # Order by creation date (newest first)
                stmt = stmt.order_by(CodeArtifactsTable.created_at.desc())

                result = await session.execute(stmt)
                artifacts = result.scalars().all()

                return [CodeArtifactSummary.model_validate(a) for a in artifacts]

        except Exception as e:
            logger.error(
                "Failed to list code artifacts",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def update_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int,
        artifact_data: CodeArtifactUpdate
    ) -> CodeArtifact:
        """Update artifact (PATCH semantics)

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Fetch existing artifact
                stmt = select(CodeArtifactsTable).where(
                    CodeArtifactsTable.id == artifact_id,
                    CodeArtifactsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                artifact_table = result.scalar_one_or_none()

                if not artifact_table:
                    raise NotFoundError(f"Code artifact {artifact_id} not found")

                # Update only provided fields (PATCH)
                update_data = artifact_data.model_dump(exclude_unset=True)

                # Ensure language is lowercase if being updated
                if "language" in update_data and update_data["language"]:
                    update_data["language"] = update_data["language"].lower()

                for field, value in update_data.items():
                    setattr(artifact_table, field, value)

                # Update timestamp
                artifact_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(artifact_table)

                return CodeArtifact.model_validate(artifact_table)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update code artifact {artifact_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "artifact_id": artifact_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> bool:
        """Delete artifact (cascade removes associations)

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Check ownership and get artifact
                stmt = select(CodeArtifactsTable).where(
                    CodeArtifactsTable.id == artifact_id,
                    CodeArtifactsTable.user_id == str(user_id)
                )

                result = await session.execute(stmt)
                artifact_table = result.scalar_one_or_none()

                if not artifact_table:
                    return False

                await session.delete(artifact_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete code artifact {artifact_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "artifact_id": artifact_id,
                    "error": str(e)
                }
            )
            raise
