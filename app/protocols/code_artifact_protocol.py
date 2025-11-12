"""
Protocol (interface) for Code Artifact Repository

Defines the contract for code artifact data access operations.
Concrete implementations must provide all methods defined here.
"""
from typing import Protocol, List
from uuid import UUID

from app.models.code_artifact_models import (
    CodeArtifact,
    CodeArtifactCreate,
    CodeArtifactUpdate,
    CodeArtifactSummary
)


class CodeArtifactRepository(Protocol):
    """Contract for Code Artifact Repository operations

    All repository implementations must provide these methods.
    Services depend on this protocol, not concrete implementations.
    """

    async def create_code_artifact(
        self,
        user_id: UUID,
        artifact_data: CodeArtifactCreate
    ) -> CodeArtifact:
        """Create a new code artifact

        Args:
            user_id: User ID for ownership
            artifact_data: CodeArtifactCreate with title, description, code, language, tags

        Returns:
            Created CodeArtifact with generated ID and timestamps

        Raises:
            ValidationError: If artifact_data is invalid
        """
        ...

    async def get_code_artifact_by_id(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> CodeArtifact | None:
        """Get a single code artifact by ID

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to retrieve

        Returns:
            CodeArtifact if found and owned by user, None otherwise
        """
        ...

    async def list_code_artifacts(
        self,
        user_id: UUID,
        project_id: int | None = None,
        language: str | None = None,
        tags: List[str] | None = None
    ) -> List[CodeArtifactSummary]:
        """List code artifacts with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            language: Optional filter by programming language (case-insensitive)
            tags: Optional filter by tags (returns artifacts with ANY of these tags)

        Returns:
            List of CodeArtifactSummary (lightweight, excludes full code content)
            Sorted by creation date (newest first)
        """
        ...

    async def update_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int,
        artifact_data: CodeArtifactUpdate
    ) -> CodeArtifact:
        """Update an existing code artifact (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to update
            artifact_data: CodeArtifactUpdate with fields to change

        Returns:
            Updated CodeArtifact

        Raises:
            NotFoundError: If artifact not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_code_artifact(
        self,
        user_id: UUID,
        artifact_id: int
    ) -> bool:
        """Delete a code artifact

        Cascade removes memory associations. Memories are preserved.

        Args:
            user_id: User ID for ownership verification
            artifact_id: Artifact ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...
