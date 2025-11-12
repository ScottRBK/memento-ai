"""
Code Artifact Service - Business logic for code artifact operations

This service implements functionality for managing code artifacts:
    - CRUD operations (create, read, update, delete)
    - Filtering and search
    - Project association
    - Memory linking (via memory service)
"""
from typing import List
from uuid import UUID

from app.config.logging_config import logging
from app.protocols.code_artifact_protocol import CodeArtifactRepository
from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate,
    CodeArtifactSummary
)
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class CodeArtifactService:
    """Service layer for code artifact operations

    Handles business logic for creating, updating, querying, and deleting code artifacts.
    Uses repository protocol for data access.
    """

    def __init__(self, artifact_repo: CodeArtifactRepository):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            artifact_repo: Code artifact repository implementing the protocol
        """
        self.artifact_repo = artifact_repo
        logger.info("Code artifact service initialized")

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
        else:
            logger.warning(
                "code artifact not found for deletion",
                extra={
                    "artifact_id": artifact_id,
                    "user_id": str(user_id)
                }
            )

        return success
