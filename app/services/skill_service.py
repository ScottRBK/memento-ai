"""Skill Service - Business logic for skill operations

This service implements functionality for managing skills:
    - CRUD operations (create, read, update, delete)
    - Semantic search
    - Import/export in Agent Skills markdown format
    - Project association
"""
from typing import TYPE_CHECKING
from uuid import UUID

import yaml

from app.config.logging_config import logging
from app.config.settings import settings
from app.exceptions import NotFoundError
from app.models.activity_models import (
    ActionType,
    ActivityEvent,
    ActorType,
    EntityType,
)
from app.models.skill_models import (
    Skill,
    SkillCreate,
    SkillSummary,
    SkillUpdate,
)
from app.protocols.skill_protocol import SkillRepository
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class SkillService:
    """Service layer for skill operations

    Handles business logic for creating, updating, querying, and deleting skills.
    Uses repository protocol for data access.
    """

    def __init__(
        self,
        skill_repo: SkillRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            skill_repo: Skill repository implementing the protocol
            event_bus: Optional event bus for activity tracking
        """
        self.skill_repo = skill_repo
        self._event_bus = event_bus
        logger.info("Skill service initialized")

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
        """Emit an activity event to the event bus.

        This is a no-op if no event bus is configured.

        Args:
            user_id: User ID for the event
            entity_type: Type of entity (skill)
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

    async def create_skill(
        self,
        user_id: UUID,
        skill_data: SkillCreate,
    ) -> Skill:
        """Create new skill

        Args:
            user_id: User ID for ownership
            skill_data: SkillCreate with name, description, content, etc.

        Returns:
            Created Skill with generated ID and timestamps
        """
        logger.info(
            "creating skill",
            extra={
                "name": skill_data.name,
                "user_id": str(user_id),
            },
        )

        skill = await self.skill_repo.create_skill(
            user_id=user_id,
            skill_data=skill_data,
        )

        logger.info(
            "skill created",
            extra={
                "skill_id": skill.id,
                "user_id": str(user_id),
            },
        )

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.SKILL,
            entity_id=skill.id,
            action=ActionType.CREATED,
            snapshot=skill.model_dump(mode="json"),
        )

        return skill

    async def get_skill(
        self,
        user_id: UUID,
        skill_id: int,
    ) -> Skill:
        """Get skill by ID with ownership verification

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to retrieve

        Returns:
            Skill with full details

        Raises:
            NotFoundError: If skill not found or not owned by user
        """
        logger.info(
            "getting skill",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        skill = await self.skill_repo.get_skill_by_id(
            user_id=user_id,
            skill_id=skill_id,
        )

        if not skill:
            raise NotFoundError(f"Skill {skill_id} not found")

        logger.info(
            "skill retrieved",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        # Emit read event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.SKILL,
                entity_id=skill_id,
                action=ActionType.READ,
                snapshot=skill.model_dump(mode="json"),
            )

        return skill

    async def list_skills(
        self,
        user_id: UUID,
        project_id: int | None = None,
        tags: list[str] | None = None,
        importance_threshold: int | None = None,
    ) -> list[SkillSummary]:
        """List skills with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            tags: Optional filter by tags (returns skills with ANY of these tags)
            importance_threshold: Optional minimum importance level

        Returns:
            List of SkillSummary (lightweight, excludes full content)
        """
        logger.info(
            "listing skills",
            extra={
                "user_id": str(user_id),
                "project_id": project_id,
                "tags": tags,
                "importance_threshold": importance_threshold,
            },
        )

        skills = await self.skill_repo.list_skills(
            user_id=user_id,
            project_id=project_id,
            tags=tags,
            importance_threshold=importance_threshold,
        )

        logger.info(
            "skills retrieved",
            extra={
                "count": len(skills),
                "user_id": str(user_id),
            },
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.SKILL,
                entity_id=0,  # Query spans multiple skills
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [s.id for s in skills],
                    "total_count": len(skills),
                },
                metadata={
                    "project_id": project_id,
                    "tags": tags,
                    "importance_threshold": importance_threshold,
                },
            )

        return skills

    async def update_skill(
        self,
        user_id: UUID,
        skill_id: int,
        skill_data: SkillUpdate,
    ) -> Skill:
        """Update existing skill (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to update
            skill_data: SkillUpdate with fields to change

        Returns:
            Updated Skill

        Raises:
            NotFoundError: If skill not found or not owned by user
        """
        logger.info(
            "updating skill",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        # Get existing skill for change detection
        existing_skill = await self.skill_repo.get_skill_by_id(
            user_id=user_id,
            skill_id=skill_id,
        )

        if not existing_skill:
            raise NotFoundError(f"Skill {skill_id} not found")

        # Detect changes
        changed_fields = get_changed_fields(
            input_model=skill_data, existing_model=existing_skill,
        )

        skill = await self.skill_repo.update_skill(
            user_id=user_id,
            skill_id=skill_id,
            skill_data=skill_data,
        )

        logger.info(
            "skill updated",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        # Emit updated event with changes
        if changed_fields:
            changes_dict = {
                field: {"old": old, "new": new}
                for field, (old, new) in changed_fields.items()
            }
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.SKILL,
                entity_id=skill_id,
                action=ActionType.UPDATED,
                snapshot=skill.model_dump(mode="json"),
                changes=changes_dict,
            )

        return skill

    async def delete_skill(
        self,
        user_id: UUID,
        skill_id: int,
    ) -> bool:
        """Delete skill

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting skill",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        # Fetch skill before deletion for snapshot
        existing_skill = await self.skill_repo.get_skill_by_id(
            user_id=user_id,
            skill_id=skill_id,
        )

        success = await self.skill_repo.delete_skill(
            user_id=user_id,
            skill_id=skill_id,
        )

        if success:
            logger.info(
                "skill deleted",
                extra={
                    "skill_id": skill_id,
                    "user_id": str(user_id),
                },
            )

            # Emit deleted event with pre-deletion snapshot
            if existing_skill:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.SKILL,
                    entity_id=skill_id,
                    action=ActionType.DELETED,
                    snapshot=existing_skill.model_dump(mode="json"),
                )
        else:
            logger.warning(
                "skill not found for deletion",
                extra={
                    "skill_id": skill_id,
                    "user_id": str(user_id),
                },
            )

        return success

    async def search_skills(
        self,
        user_id: UUID,
        query: str,
        k: int = 5,
        project_id: int | None = None,
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
        logger.info(
            "searching skills",
            extra={
                "user_id": str(user_id),
                "query": query[:50],
                "k": k,
                "project_id": project_id,
            },
        )

        results = await self.skill_repo.search_skills(
            user_id=user_id,
            query=query,
            k=k,
            project_id=project_id,
        )

        logger.info(
            "skill search completed",
            extra={
                "count": len(results),
                "user_id": str(user_id),
            },
        )

        return results

    async def import_skill(
        self,
        user_id: UUID,
        skill_md_content: str,
        project_id: int | None = None,
        importance: int = 7,
    ) -> Skill:
        """Import a skill from Agent Skills markdown format

        Parses YAML frontmatter between --- delimiters and extracts
        standard fields per the Agent Skills specification.

        Args:
            user_id: User ID for ownership
            skill_md_content: Raw SKILL.md content with YAML frontmatter
            project_id: Optional project association (overrides frontmatter)
            importance: Importance level (default: 7)

        Returns:
            Created Skill

        Raises:
            ValueError: If frontmatter is missing or malformed
        """
        logger.info(
            "importing skill from markdown",
            extra={"user_id": str(user_id)},
        )

        # Parse YAML frontmatter between --- delimiters
        parts = skill_md_content.split("---", 2)
        if len(parts) < 3:
            raise ValueError(
                "Invalid skill markdown: expected YAML frontmatter between --- delimiters",
            )

        frontmatter_raw = parts[1].strip()
        body = parts[2].strip()

        frontmatter = yaml.safe_load(frontmatter_raw)
        if not isinstance(frontmatter, dict):
            raise ValueError("Invalid YAML frontmatter: expected a mapping")

        # Extract standard fields
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        skill_license = frontmatter.get("license")
        compatibility = frontmatter.get("compatibility")
        metadata = frontmatter.get("metadata")

        # Map allowed-tools (hyphenated standard) to allowed_tools (underscored)
        allowed_tools = frontmatter.get("allowed-tools")

        if not name:
            raise ValueError("Skill frontmatter must include 'name'")
        if not description:
            raise ValueError("Skill frontmatter must include 'description'")

        skill_data = SkillCreate(
            name=name,
            description=description,
            content=body,
            license=skill_license,
            compatibility=compatibility,
            allowed_tools=allowed_tools,
            metadata=metadata,
            importance=importance,
            project_id=project_id,
        )

        return await self.create_skill(user_id=user_id, skill_data=skill_data)

    async def export_skill(
        self,
        user_id: UUID,
        skill_id: int,
    ) -> str:
        """Export a skill to Agent Skills markdown format

        Builds YAML frontmatter from standard fields and appends
        the content as the markdown body.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill ID to export

        Returns:
            Formatted SKILL.md string with YAML frontmatter

        Raises:
            NotFoundError: If skill not found or not owned by user
        """
        logger.info(
            "exporting skill to markdown",
            extra={
                "skill_id": skill_id,
                "user_id": str(user_id),
            },
        )

        skill = await self.get_skill(user_id=user_id, skill_id=skill_id)

        # Build frontmatter dict with only non-None standard fields
        frontmatter: dict = {}

        frontmatter["name"] = skill.name
        frontmatter["description"] = skill.description

        if skill.license is not None:
            frontmatter["license"] = skill.license
        if skill.compatibility is not None:
            frontmatter["compatibility"] = skill.compatibility
        if skill.metadata is not None:
            frontmatter["metadata"] = skill.metadata
        # Map allowed_tools (underscored) back to allowed-tools (hyphenated)
        if skill.allowed_tools is not None:
            frontmatter["allowed-tools"] = skill.allowed_tools

        frontmatter_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ).strip()

        return f"---\n{frontmatter_str}\n---\n\n{skill.content}\n"

    async def link_skill_to_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Link a skill to a memory.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to link
            memory_id: Memory to link to

        Returns:
            Confirmation dict with linked IDs
        """
        # Verify skill exists
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.link_skill_to_memory(
            user_id=user_id,
            skill_id=skill_id,
            memory_id=memory_id,
        )

    async def unlink_skill_from_memory(
        self,
        user_id: UUID,
        skill_id: int,
        memory_id: int,
    ) -> dict:
        """Unlink a skill from a memory.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to unlink
            memory_id: Memory to unlink from

        Returns:
            Confirmation dict
        """
        # Verify skill exists
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.unlink_skill_from_memory(
            user_id=user_id,
            skill_id=skill_id,
            memory_id=memory_id,
        )

    async def link_skill_to_file(
        self,
        user_id: UUID,
        skill_id: int,
        file_id: int,
    ) -> dict:
        """Link a skill to a file.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to link
            file_id: File to link to

        Returns:
            Confirmation dict with linked IDs
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.link_skill_to_file(
            user_id=user_id,
            skill_id=skill_id,
            file_id=file_id,
        )

    async def unlink_skill_from_file(
        self,
        user_id: UUID,
        skill_id: int,
        file_id: int,
    ) -> dict:
        """Unlink a skill from a file.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to unlink
            file_id: File to unlink from

        Returns:
            Confirmation dict
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.unlink_skill_from_file(
            user_id=user_id,
            skill_id=skill_id,
            file_id=file_id,
        )

    async def link_skill_to_code_artifact(
        self,
        user_id: UUID,
        skill_id: int,
        code_artifact_id: int,
    ) -> dict:
        """Link a skill to a code artifact.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to link
            code_artifact_id: Code artifact to link to

        Returns:
            Confirmation dict with linked IDs
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.link_skill_to_code_artifact(
            user_id=user_id,
            skill_id=skill_id,
            code_artifact_id=code_artifact_id,
        )

    async def unlink_skill_from_code_artifact(
        self,
        user_id: UUID,
        skill_id: int,
        code_artifact_id: int,
    ) -> dict:
        """Unlink a skill from a code artifact.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to unlink
            code_artifact_id: Code artifact to unlink from

        Returns:
            Confirmation dict
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.unlink_skill_from_code_artifact(
            user_id=user_id,
            skill_id=skill_id,
            code_artifact_id=code_artifact_id,
        )

    async def link_skill_to_document(
        self,
        user_id: UUID,
        skill_id: int,
        document_id: int,
    ) -> dict:
        """Link a skill to a document.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to link
            document_id: Document to link to

        Returns:
            Confirmation dict with linked IDs
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.link_skill_to_document(
            user_id=user_id,
            skill_id=skill_id,
            document_id=document_id,
        )

    async def unlink_skill_from_document(
        self,
        user_id: UUID,
        skill_id: int,
        document_id: int,
    ) -> dict:
        """Unlink a skill from a document.

        Args:
            user_id: User ID for ownership verification
            skill_id: Skill to unlink
            document_id: Document to unlink from

        Returns:
            Confirmation dict
        """
        await self.get_skill(user_id=user_id, skill_id=skill_id)

        return await self.skill_repo.unlink_skill_from_document(
            user_id=user_id,
            skill_id=skill_id,
            document_id=document_id,
        )
