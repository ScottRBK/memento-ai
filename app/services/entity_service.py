"""
Entity Service - Business logic for entity and entity relationship operations

This service implements functionality for managing entities and their relationships:
    - Entity CRUD operations (create, read, update, delete)
    - Entity filtering and search
    - Project association
    - Memory linking
    - Entity relationship management (knowledge graph)
"""
from typing import TYPE_CHECKING, List
from uuid import UUID

from app.config.logging_config import logging
from app.config.settings import settings
from app.models.activity_models import (
    ActivityEvent,
    ActorType,
    ActionType,
    EntityType as ActivityEntityType,  # Alias to avoid conflict with entity_models.EntityType
)
from app.protocols.entity_protocol import EntityRepository
from app.models.entity_models import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntitySummary,
    EntityRelationship,
    EntityRelationshipCreate,
    EntityRelationshipUpdate,
    EntityType
)
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class EntityService:
    """Service layer for entity and entity relationship operations

    Handles business logic for creating, updating, querying, and deleting entities
    and their relationships. Uses repository protocol for data access.
    """

    def __init__(
        self,
        entity_repo: EntityRepository,
        event_bus: "EventBus | None" = None,
    ):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            entity_repo: Entity repository implementing the protocol
            event_bus: Optional event bus for activity tracking
        """
        self.entity_repo = entity_repo
        self._event_bus = event_bus
        logger.info("Entity service initialized")

    async def _emit_event(
        self,
        user_id: UUID,
        entity_type: ActivityEntityType,
        entity_id: int,
        action: ActionType,
        snapshot: dict,
        changes: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Emit an activity event to the event bus.

        This is a no-op if no event bus is configured.

        Args:
            user_id: User ID for the event
            entity_type: Type of entity (entity, entity_memory_link, entity_relationship)
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

    # Entity CRUD operations

    async def create_entity(
        self,
        user_id: UUID,
        entity_data: EntityCreate
    ) -> Entity:
        """Create new entity

        Args:
            user_id: User ID for ownership
            entity_data: EntityCreate with name, type, notes, etc.

        Returns:
            Created Entity with generated ID and timestamps
        """
        logger.info(
            "creating entity",
            extra={
                "entity_name": entity_data.name[:50],
                "entity_type": entity_data.entity_type.value,
                "user_id": str(user_id)
            }
        )

        entity = await self.entity_repo.create_entity(
            user_id=user_id,
            entity_data=entity_data
        )

        logger.info(
            "entity created",
            extra={
                "entity_id": entity.id,
                "user_id": str(user_id)
            }
        )

        # Emit created event
        await self._emit_event(
            user_id=user_id,
            entity_type=ActivityEntityType.ENTITY,
            entity_id=entity.id,
            action=ActionType.CREATED,
            snapshot=entity.model_dump(mode="json"),
        )

        return entity

    async def get_entity(
        self,
        user_id: UUID,
        entity_id: int
    ) -> Entity:
        """Get entity by ID with ownership verification

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to retrieve

        Returns:
            Entity with full details

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        logger.info(
            "getting entity",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        entity = await self.entity_repo.get_entity_by_id(
            user_id=user_id,
            entity_id=entity_id
        )

        if not entity:
            raise NotFoundError(f"Entity {entity_id} not found")

        logger.info(
            "entity retrieved",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        # Emit read event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY,
                entity_id=entity_id,
                action=ActionType.READ,
                snapshot=entity.model_dump(mode="json"),
            )

        return entity

    async def list_entities(
        self,
        user_id: UUID,
        project_ids: List[int] | None = None,
        entity_type: EntityType | None = None,
        tags: List[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[EntitySummary], int]:
        """List entities with optional filtering and pagination

        Args:
            user_id: User ID for ownership filtering
            project_ids: Optional filter by projects (returns entities associated with ANY of these projects)
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY of these tags)
            limit: Maximum number of entities to return (default 20)
            offset: Number of entities to skip (default 0)

        Returns:
            Tuple of (entities, total_count) where:
            - entities: List of EntitySummary (lightweight, excludes notes)
            - total_count: Total matching entities before pagination
        """
        logger.info(
            "listing entities",
            extra={
                "user_id": str(user_id),
                "project_ids": project_ids,
                "entity_type": entity_type.value if entity_type else None,
                "tags": tags,
                "limit": limit,
                "offset": offset
            }
        )

        entities, total = await self.entity_repo.list_entities(
            user_id=user_id,
            project_ids=project_ids,
            entity_type=entity_type,
            tags=tags,
            limit=limit,
            offset=offset
        )

        logger.info(
            "entities retrieved",
            extra={
                "count": len(entities),
                "total": total,
                "user_id": str(user_id)
            }
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY,
                entity_id=0,  # Query spans multiple entities
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [e.id for e in entities],
                    "total_count": total,
                },
                metadata={
                    "project_ids": project_ids,
                    "entity_type": entity_type.value if entity_type else None,
                    "tags": tags,
                    "limit": limit,
                    "offset": offset,
                },
            )

        return entities, total

    async def search_entities(
        self,
        user_id: UUID,
        search_query: str,
        entity_type: EntityType | None = None,
        tags: List[str] | None = None,
        limit: int = 20
    ) -> List[EntitySummary]:
        """Search entities by name using text matching

        Args:
            user_id: User ID for ownership filtering
            search_query: Text to search for in entity name
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY of these tags)
            limit: Maximum number of results to return

        Returns:
            List of EntitySummary matching the search
        """
        logger.info(
            "searching entities",
            extra={
                "user_id": str(user_id),
                "query": search_query,
                "entity_type": entity_type.value if entity_type else None,
                "tags": tags,
                "limit": limit
            }
        )

        entities = await self.entity_repo.search_entities(
            user_id=user_id,
            search_query=search_query,
            entity_type=entity_type,
            tags=tags,
            limit=limit
        )

        logger.info(
            "entity search completed",
            extra={
                "count": len(entities),
                "user_id": str(user_id)
            }
        )

        # Emit queried event (opt-in via ACTIVITY_TRACK_READS)
        if settings.ACTIVITY_TRACK_READS and self._event_bus:
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY,
                entity_id=0,  # Query spans multiple entities
                action=ActionType.QUERIED,
                snapshot={
                    "result_ids": [e.id for e in entities],
                    "total_count": len(entities),
                },
                metadata={
                    "search_query": search_query,
                    "entity_type": entity_type.value if entity_type else None,
                    "tags": tags,
                    "limit": limit,
                },
            )

        return entities

    async def update_entity(
        self,
        user_id: UUID,
        entity_id: int,
        entity_data: EntityUpdate
    ) -> Entity:
        """Update existing entity (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to update
            entity_data: EntityUpdate with fields to change

        Returns:
            Updated Entity

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        logger.info(
            "updating entity",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        # Get existing entity for change detection
        existing_entity = await self.entity_repo.get_entity_by_id(
            user_id=user_id,
            entity_id=entity_id
        )

        if not existing_entity:
            raise NotFoundError(f"Entity {entity_id} not found")

        # Detect changes
        changed_fields = get_changed_fields(
            input_model=entity_data, existing_model=existing_entity
        )

        entity = await self.entity_repo.update_entity(
            user_id=user_id,
            entity_id=entity_id,
            entity_data=entity_data
        )

        logger.info(
            "entity updated",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        # Emit updated event with changes
        if changed_fields:
            changes_dict = {
                field: {"old": old, "new": new}
                for field, (old, new) in changed_fields.items()
            }
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY,
                entity_id=entity_id,
                action=ActionType.UPDATED,
                snapshot=entity.model_dump(mode="json"),
                changes=changes_dict,
            )

        return entity

    async def delete_entity(
        self,
        user_id: UUID,
        entity_id: int
    ) -> bool:
        """Delete entity (cascade removes memory associations and relationships)

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting entity",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        # Fetch entity before deletion for snapshot
        existing_entity = await self.entity_repo.get_entity_by_id(
            user_id=user_id,
            entity_id=entity_id
        )

        success = await self.entity_repo.delete_entity(
            user_id=user_id,
            entity_id=entity_id
        )

        if success:
            logger.info(
                "entity deleted",
                extra={
                    "entity_id": entity_id,
                    "user_id": str(user_id)
                }
            )

            # Emit deleted event with pre-deletion snapshot
            if existing_entity:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=ActivityEntityType.ENTITY,
                    entity_id=entity_id,
                    action=ActionType.DELETED,
                    snapshot=existing_entity.model_dump(mode="json"),
                )
        else:
            logger.warning(
                "entity not found for deletion",
                extra={
                    "entity_id": entity_id,
                    "user_id": str(user_id)
                }
            )

        return success

    # Entity-Memory linking operations

    async def link_entity_to_memory(
        self,
        user_id: UUID,
        entity_id: int,
        memory_id: int
    ) -> bool:
        """Link entity to memory

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to link
            memory_id: Memory ID to link

        Returns:
            True if linked (or already linked)

        Raises:
            NotFoundError: If entity or memory not found or not owned by user
        """
        logger.info(
            "linking entity to memory",
            extra={
                "entity_id": entity_id,
                "memory_id": memory_id,
                "user_id": str(user_id)
            }
        )

        success = await self.entity_repo.link_entity_to_memory(
            user_id=user_id,
            entity_id=entity_id,
            memory_id=memory_id
        )

        logger.info(
            "entity linked to memory",
            extra={
                "entity_id": entity_id,
                "memory_id": memory_id,
                "user_id": str(user_id)
            }
        )

        # Emit entity-memory link created event
        if success:
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY_MEMORY_LINK,
                entity_id=0,  # Links use metadata for source/target
                action=ActionType.CREATED,
                snapshot={"entity_id": entity_id, "memory_id": memory_id},
                metadata={"entity_id": entity_id, "memory_id": memory_id},
            )

        return success

    async def unlink_entity_from_memory(
        self,
        user_id: UUID,
        entity_id: int,
        memory_id: int
    ) -> bool:
        """Unlink entity from memory

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to unlink
            memory_id: Memory ID to unlink

        Returns:
            True if unlinked, False if link didn't exist or entity/memory not found
        """
        logger.info(
            "unlinking entity from memory",
            extra={
                "entity_id": entity_id,
                "memory_id": memory_id,
                "user_id": str(user_id)
            }
        )

        success = await self.entity_repo.unlink_entity_from_memory(
            user_id=user_id,
            entity_id=entity_id,
            memory_id=memory_id
        )

        if success:
            logger.info(
                "entity unlinked from memory",
                extra={
                    "entity_id": entity_id,
                    "memory_id": memory_id,
                    "user_id": str(user_id)
                }
            )

            # Emit entity-memory link deleted event
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY_MEMORY_LINK,
                entity_id=0,  # Links use metadata for source/target
                action=ActionType.DELETED,
                snapshot={"entity_id": entity_id, "memory_id": memory_id},
                metadata={"entity_id": entity_id, "memory_id": memory_id},
            )
        else:
            logger.warning(
                "entity-memory link not found",
                extra={
                    "entity_id": entity_id,
                    "memory_id": memory_id,
                    "user_id": str(user_id)
                }
            )

        return success

    # Entity-Project linking operations

    async def link_entity_to_project(
        self,
        user_id: UUID,
        entity_id: int,
        project_id: int
    ) -> bool:
        """Link entity to project

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to link
            project_id: Project ID to link

        Returns:
            True if linked (or already linked)

        Raises:
            NotFoundError: If entity or project not found or not owned by user
        """
        logger.info(
            "linking entity to project",
            extra={
                "entity_id": entity_id,
                "project_id": project_id,
                "user_id": str(user_id)
            }
        )

        success = await self.entity_repo.link_entity_to_project(
            user_id=user_id,
            entity_id=entity_id,
            project_id=project_id
        )

        logger.info(
            "entity linked to project",
            extra={
                "entity_id": entity_id,
                "project_id": project_id,
                "user_id": str(user_id)
            }
        )

        # Emit entity-project link created event
        if success:
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY_PROJECT_LINK,
                entity_id=0,  # Links use metadata for source/target
                action=ActionType.CREATED,
                snapshot={"entity_id": entity_id, "project_id": project_id},
                metadata={"entity_id": entity_id, "project_id": project_id},
            )

        return success

    async def unlink_entity_from_project(
        self,
        user_id: UUID,
        entity_id: int,
        project_id: int
    ) -> bool:
        """Unlink entity from project

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to unlink
            project_id: Project ID to unlink

        Returns:
            True if unlinked, False if link didn't exist or entity/project not found
        """
        logger.info(
            "unlinking entity from project",
            extra={
                "entity_id": entity_id,
                "project_id": project_id,
                "user_id": str(user_id)
            }
        )

        success = await self.entity_repo.unlink_entity_from_project(
            user_id=user_id,
            entity_id=entity_id,
            project_id=project_id
        )

        if success:
            logger.info(
                "entity unlinked from project",
                extra={
                    "entity_id": entity_id,
                    "project_id": project_id,
                    "user_id": str(user_id)
                }
            )

            # Emit entity-project link deleted event
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY_PROJECT_LINK,
                entity_id=0,  # Links use metadata for source/target
                action=ActionType.DELETED,
                snapshot={"entity_id": entity_id, "project_id": project_id},
                metadata={"entity_id": entity_id, "project_id": project_id},
            )
        else:
            logger.warning(
                "entity-project link not found",
                extra={
                    "entity_id": entity_id,
                    "project_id": project_id,
                    "user_id": str(user_id)
                }
            )

        return success

    # Entity Relationship operations

    async def create_entity_relationship(
        self,
        user_id: UUID,
        relationship_data: EntityRelationshipCreate
    ) -> EntityRelationship:
        """Create relationship between two entities

        Args:
            user_id: User ID for ownership verification
            relationship_data: EntityRelationshipCreate with relationship details

        Returns:
            Created EntityRelationship with generated ID and timestamps

        Raises:
            NotFoundError: If source or target entity not found or not owned by user
        """
        logger.info(
            "creating entity relationship",
            extra={
                "source_entity_id": relationship_data.source_entity_id,
                "target_entity_id": relationship_data.target_entity_id,
                "relationship_type": relationship_data.relationship_type,
                "user_id": str(user_id)
            }
        )

        relationship = await self.entity_repo.create_entity_relationship(
            user_id=user_id,
            relationship_data=relationship_data
        )

        logger.info(
            "entity relationship created",
            extra={
                "relationship_id": relationship.id,
                "user_id": str(user_id)
            }
        )

        # Emit entity relationship created event
        await self._emit_event(
            user_id=user_id,
            entity_type=ActivityEntityType.ENTITY_RELATIONSHIP,
            entity_id=relationship.id,
            action=ActionType.CREATED,
            snapshot=relationship.model_dump(mode="json"),
        )

        return relationship

    async def get_entity_relationships(
        self,
        user_id: UUID,
        entity_id: int,
        direction: str | None = None,
        relationship_type: str | None = None
    ) -> List[EntityRelationship]:
        """Get relationships for an entity

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to get relationships for
            direction: Optional filter: "outgoing", "incoming", or None (both)
            relationship_type: Optional filter by relationship type

        Returns:
            List of EntityRelationship sorted by creation date (newest first)

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        logger.info(
            "getting entity relationships",
            extra={
                "entity_id": entity_id,
                "direction": direction,
                "relationship_type": relationship_type,
                "user_id": str(user_id)
            }
        )

        relationships = await self.entity_repo.get_entity_relationships(
            user_id=user_id,
            entity_id=entity_id,
            direction=direction,
            relationship_type=relationship_type
        )

        logger.info(
            "entity relationships retrieved",
            extra={
                "count": len(relationships),
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        # Note: Optional READ event for relationships could be added here
        # but skipping for now as graph operations are high-volume

        return relationships

    async def update_entity_relationship(
        self,
        user_id: UUID,
        relationship_id: int,
        relationship_data: EntityRelationshipUpdate
    ) -> EntityRelationship:
        """Update entity relationship (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            relationship_id: Relationship ID to update
            relationship_data: EntityRelationshipUpdate with fields to change

        Returns:
            Updated EntityRelationship

        Raises:
            NotFoundError: If relationship not found or not owned by user
        """
        logger.info(
            "updating entity relationship",
            extra={
                "relationship_id": relationship_id,
                "user_id": str(user_id)
            }
        )

        # Note: The repo doesn't have a direct get_relationship_by_id, so we'll emit
        # the event unconditionally without a changes dict

        relationship = await self.entity_repo.update_entity_relationship(
            user_id=user_id,
            relationship_id=relationship_id,
            relationship_data=relationship_data
        )

        logger.info(
            "entity relationship updated",
            extra={
                "relationship_id": relationship_id,
                "user_id": str(user_id)
            }
        )

        # Emit entity relationship updated event
        # Note: Change detection would require fetching the relationship first
        # For now, emit the event without changes dict
        await self._emit_event(
            user_id=user_id,
            entity_type=ActivityEntityType.ENTITY_RELATIONSHIP,
            entity_id=relationship_id,
            action=ActionType.UPDATED,
            snapshot=relationship.model_dump(mode="json"),
        )

        return relationship

    async def delete_entity_relationship(
        self,
        user_id: UUID,
        relationship_id: int
    ) -> bool:
        """Delete entity relationship

        Args:
            user_id: User ID for ownership verification
            relationship_id: Relationship ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        logger.info(
            "deleting entity relationship",
            extra={
                "relationship_id": relationship_id,
                "user_id": str(user_id)
            }
        )

        # Note: We can't easily fetch the relationship before deletion without
        # a get_relationship_by_id method, so snapshot will be minimal

        success = await self.entity_repo.delete_entity_relationship(
            user_id=user_id,
            relationship_id=relationship_id
        )

        if success:
            logger.info(
                "entity relationship deleted",
                extra={
                    "relationship_id": relationship_id,
                    "user_id": str(user_id)
                }
            )

            # Emit entity relationship deleted event
            await self._emit_event(
                user_id=user_id,
                entity_type=ActivityEntityType.ENTITY_RELATIONSHIP,
                entity_id=relationship_id,
                action=ActionType.DELETED,
                snapshot={"id": relationship_id},  # Minimal snapshot
            )
        else:
            logger.warning(
                "entity relationship not found for deletion",
                extra={
                    "relationship_id": relationship_id,
                    "user_id": str(user_id)
                }
            )

        return success

    # Graph visualization operations

    async def get_all_entity_relationships(
        self,
        user_id: UUID
    ) -> List[EntityRelationship]:
        """Get all entity relationships for graph visualization

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of all EntityRelationship owned by user
        """
        logger.info(
            "getting all entity relationships for graph",
            extra={"user_id": str(user_id)}
        )

        relationships = await self.entity_repo.get_all_entity_relationships(
            user_id=user_id
        )

        logger.info(
            "entity relationships retrieved for graph",
            extra={
                "count": len(relationships),
                "user_id": str(user_id)
            }
        )

        return relationships

    async def get_all_entity_memory_links(
        self,
        user_id: UUID
    ) -> List[tuple[int, int]]:
        """Get all entity-memory links for graph visualization

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of (entity_id, memory_id) tuples
        """
        logger.info(
            "getting all entity-memory links for graph",
            extra={"user_id": str(user_id)}
        )

        links = await self.entity_repo.get_all_entity_memory_links(
            user_id=user_id
        )

        logger.info(
            "entity-memory links retrieved for graph",
            extra={
                "count": len(links),
                "user_id": str(user_id)
            }
        )

        return links

    async def get_all_entity_project_links(
        self,
        user_id: UUID
    ) -> List[tuple[int, int]]:
        """Get all entity-project links for graph visualization

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of (entity_id, project_id) tuples
        """
        logger.info(
            "getting all entity-project links for graph",
            extra={"user_id": str(user_id)}
        )

        links = await self.entity_repo.get_all_entity_project_links(
            user_id=user_id
        )

        logger.info(
            "entity-project links retrieved for graph",
            extra={
                "count": len(links),
                "user_id": str(user_id)
            }
        )

        return links

    async def get_entity_memories(
        self,
        user_id: UUID,
        entity_id: int
    ) -> tuple[List[int], int]:
        """Get all memories linked to a specific entity

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to get memories for

        Returns:
            Tuple of (memory_ids_list, count)

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        logger.info(
            "getting memories for entity",
            extra={
                "entity_id": entity_id,
                "user_id": str(user_id)
            }
        )

        memory_ids = await self.entity_repo.get_entity_memories(
            user_id=user_id,
            entity_id=entity_id
        )

        logger.info(
            "entity memories retrieved",
            extra={
                "entity_id": entity_id,
                "count": len(memory_ids),
                "user_id": str(user_id)
            }
        )

        return memory_ids, len(memory_ids)
