"""
Protocol (interface) for Skill Repository

Defines the contract for skill data access operations.
Concrete implementations must provide all methods defined here.
"""
from typing import Protocol
from uuid import UUID

from app.models.skill_models import (
    Skill,
    SkillCreate,
    SkillUpdate,
    SkillSummary
)


class SkillRepository(Protocol):
    """Contract for Skill Repository operations

    All repository implementations must provide these methods.
    Services depend on this protocol, not concrete implementations.
    """

    async def create_skill(
        self,
        user_id: UUID,
        skill_data: SkillCreate
    ) -> Skill:
        """Create a new skill

        Args:
            user_id: User ID for ownership
            skill_data: SkillCreate with title, description, content, etc.

        Returns:
            Created Skill with generated ID and timestamps

        Raises:
            ValidationError: If skill_data is invalid
        """
        ...

    async def get_skill_by_id(
        self,
        user_id: UUID,
        skill_id: int
    ) -> Skill | None:
        """Get a single skill by ID

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to retrieve

        Returns:
            Skill if found and owned by user, None otherwise
        """
        ...

    async def list_skills(
        self,
        user_id: UUID,
        project_id: int | None = None,
        tags: list[str] | None = None,
        importance_threshold: int | None = None
    ) -> list[SkillSummary]:
        """List skills with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            tags: Optional filter by tags (returns skills with ANY of these tags)
            importance_threshold: Optional minimum importance level

        Returns:
            List of SkillSummary (lightweight, excludes full content)
            Sorted by creation date (newest first)
        """
        ...

    async def update_skill(
        self,
        user_id: UUID,
        skill_id: int,
        skill_data: SkillUpdate
    ) -> Skill:
        """Update an existing skill (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to update
            skill_data: SkillUpdate with fields to change

        Returns:
            Updated Skill

        Raises:
            NotFoundError: If skill not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_skill(
        self,
        user_id: UUID,
        skill_id: int
    ) -> bool:
        """Delete a skill

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...

    async def search_skills(
        self,
        user_id: UUID,
        query: str,
        k: int = 5,
        project_id: int | None = None
    ) -> list[SkillSummary]:
        """Search skills by semantic similarity

        Args:
            user_id: User ID for ownership filtering
            query: Search query string
            k: Number of results to return (default: 5)
            project_id: Optional filter by project

        Returns:
            List of SkillSummary ranked by relevance
        """
        ...

    async def link_skill_to_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Link a skill to a memory via the association table."""
        ...

    async def unlink_skill_from_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Unlink a skill from a memory."""
        ...
