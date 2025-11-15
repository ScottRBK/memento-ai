"""
Entity Service - Business logic for entity and entity relationship operations

This service implements functionality for managing entities and their relationships:
    - Entity CRUD operations (create, read, update, delete)
    - Entity filtering and search
    - Project association
    - Memory linking
    - Entity relationship management (knowledge graph)
"""
from typing import List
from uuid import UUID

from app.config.logging_config import logging
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

logger = logging.getLogger(__name__)


class EntityService:
    """Service layer for entity and entity relationship operations

    Handles business logic for creating, updating, querying, and deleting entities
    and their relationships. Uses repository protocol for data access.
    """

    def __init__(self, entity_repo: EntityRepository):
        """Initialize with repository protocol (not concrete implementation)

        Args:
            entity_repo: Entity repository implementing the protocol
        """
        self.entity_repo = entity_repo
        logger.info("Entity service initialized")

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

        return entity

    async def list_entities(
        self,
        user_id: UUID,
        project_id: int | None = None,
        entity_type: EntityType | None = None,
        tags: List[str] | None = None
    ) -> List[EntitySummary]:
        """List entities with optional filtering

        Args:
            user_id: User ID for ownership filtering
            project_id: Optional filter by project
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY of these tags)

        Returns:
            List of EntitySummary (lightweight, excludes notes)
        """
        logger.info(
            "listing entities",
            extra={
                "user_id": str(user_id),
                "project_id": project_id,
                "entity_type": entity_type.value if entity_type else None,
                "tags": tags
            }
        )

        entities = await self.entity_repo.list_entities(
            user_id=user_id,
            project_id=project_id,
            entity_type=entity_type,
            tags=tags
        )

        logger.info(
            "entities retrieved",
            extra={
                "count": len(entities),
                "user_id": str(user_id)
            }
        )

        return entities

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
        else:
            logger.warning(
                "entity relationship not found for deletion",
                extra={
                    "relationship_id": relationship_id,
                    "user_id": str(user_id)
                }
            )

        return success
