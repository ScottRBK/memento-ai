"""
Protocol (interface) for Entity Repository

Defines the contract for entity and entity relationship data access operations.
Concrete implementations must provide all methods defined here.
"""
from typing import Protocol, List
from uuid import UUID

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


class EntityRepository(Protocol):
    """Contract for Entity Repository operations

    All repository implementations must provide these methods.
    Services depend on this protocol, not concrete implementations.
    """

    # Entity CRUD operations

    async def create_entity(
        self,
        user_id: UUID,
        entity_data: EntityCreate
    ) -> Entity:
        """Create a new entity

        Args:
            user_id: User ID for ownership
            entity_data: EntityCreate with name, type, notes, etc.

        Returns:
            Created Entity with generated ID and timestamps

        Raises:
            ValidationError: If entity_data is invalid
        """
        ...

    async def get_entity_by_id(
        self,
        user_id: UUID,
        entity_id: int
    ) -> Entity | None:
        """Get a single entity by ID

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to retrieve

        Returns:
            Entity if found and owned by user, None otherwise
        """
        ...

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
            entity_type: Optional filter by entity type (Organization, Individual, etc.)
            tags: Optional filter by tags (returns entities with ANY of these tags)

        Returns:
            List of EntitySummary (lightweight, excludes notes)
            Sorted by creation date (newest first)
        """
        ...

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
            Sorted by creation date (newest first)
        """
        ...

    async def update_entity(
        self,
        user_id: UUID,
        entity_id: int,
        entity_data: EntityUpdate
    ) -> Entity:
        """Update an existing entity (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to update
            entity_data: EntityUpdate with fields to change

        Returns:
            Updated Entity

        Raises:
            NotFoundError: If entity not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_entity(
        self,
        user_id: UUID,
        entity_id: int
    ) -> bool:
        """Delete an entity

        Cascade removes memory associations and entity relationships. Memories are preserved.

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...

    # Entity-Memory linking operations

    async def link_entity_to_memory(
        self,
        user_id: UUID,
        entity_id: int,
        memory_id: int
    ) -> bool:
        """Link an entity to a memory

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to link
            memory_id: Memory ID to link

        Returns:
            True if linked (or already linked), False if entity or memory not found

        Raises:
            NotFoundError: If entity or memory not found or not owned by user
        """
        ...

    async def unlink_entity_from_memory(
        self,
        user_id: UUID,
        entity_id: int,
        memory_id: int
    ) -> bool:
        """Unlink an entity from a memory

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to unlink
            memory_id: Memory ID to unlink

        Returns:
            True if unlinked, False if link didn't exist or entity/memory not found
        """
        ...

    # Entity Relationship operations

    async def create_entity_relationship(
        self,
        user_id: UUID,
        relationship_data: EntityRelationshipCreate
    ) -> EntityRelationship:
        """Create a relationship between two entities

        Args:
            user_id: User ID for ownership verification
            relationship_data: EntityRelationshipCreate with source, target, type, etc.

        Returns:
            Created EntityRelationship with generated ID and timestamps

        Raises:
            NotFoundError: If source or target entity not found or not owned by user
            ValidationError: If relationship_data is invalid
        """
        ...

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
            relationship_type: Optional filter by relationship type (e.g., "works_at")

        Returns:
            List of EntityRelationship
            Sorted by creation date (newest first)

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        ...

    async def update_entity_relationship(
        self,
        user_id: UUID,
        relationship_id: int,
        relationship_data: EntityRelationshipUpdate
    ) -> EntityRelationship:
        """Update an entity relationship (PATCH semantics)

        Only provided fields are updated. None/omitted fields remain unchanged.

        Args:
            user_id: User ID for ownership verification
            relationship_id: Relationship ID to update
            relationship_data: EntityRelationshipUpdate with fields to change

        Returns:
            Updated EntityRelationship

        Raises:
            NotFoundError: If relationship not found or not owned by user
            ValidationError: If update data is invalid
        """
        ...

    async def delete_entity_relationship(
        self,
        user_id: UUID,
        relationship_id: int
    ) -> bool:
        """Delete an entity relationship

        Args:
            user_id: User ID for ownership verification
            relationship_id: Relationship ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        ...
