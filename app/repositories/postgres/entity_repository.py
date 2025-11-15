"""
PostgreSQL repository for Entity and EntityRelationship data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, and_

from app.repositories.postgres.postgres_tables import (
    EntitiesTable,
    EntityRelationshipsTable,
    MemoryTable
)
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
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
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class PostgresEntityRepository:
    """Repository for Entity and EntityRelationship operations in PostgreSQL"""

    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        """Initialize with database adapter

        Args:
            db_adapter: PostgreSQL database adapter for session management
        """
        self.db_adapter = db_adapter
        logger.info("Postgres entity repository initialized")

    # Entity CRUD operations

    async def create_entity(
        self,
        user_id: UUID,
        entity_data: EntityCreate
    ) -> Entity:
        """Create new entity

        Args:
            user_id: User ID for ownership
            entity_data: EntityCreate with entity details

        Returns:
            Created Entity with generated ID and timestamps
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Create ORM model from Pydantic
                entity_table = EntitiesTable(
                    user_id=user_id,
                    name=entity_data.name,
                    entity_type=entity_data.entity_type.value,  # Convert enum to string
                    custom_type=entity_data.custom_type,
                    notes=entity_data.notes,
                    tags=entity_data.tags,
                    project_id=entity_data.project_id
                )

                session.add(entity_table)
                await session.commit()
                await session.refresh(entity_table)

                # Convert ORM to Pydantic
                return Entity.model_validate(entity_table)

        except Exception as e:
            logger.error(
                "Failed to create entity",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_entity_by_id(
        self,
        user_id: UUID,
        entity_id: int
    ) -> Entity | None:
        """Get entity by ID with ownership check

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to retrieve

        Returns:
            Entity if found and owned by user, None otherwise
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Query with ownership check
                stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )

                result = await session.execute(stmt)
                entity_table = result.scalar_one_or_none()

                if not entity_table:
                    return None

                return Entity.model_validate(entity_table)

        except Exception as e:
            logger.error(
                f"Failed to get entity {entity_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Build query with filters
                stmt = select(EntitiesTable).where(
                    EntitiesTable.user_id == user_id
                )

                if project_id is not None:
                    stmt = stmt.where(EntitiesTable.project_id == project_id)

                if entity_type:
                    stmt = stmt.where(EntitiesTable.entity_type == entity_type.value)

                if tags:
                    # GIN array overlap search - finds entities with ANY of the provided tags
                    stmt = stmt.where(EntitiesTable.tags.overlap(tags))

                # Order by creation date (newest first)
                stmt = stmt.order_by(EntitiesTable.created_at.desc())

                result = await session.execute(stmt)
                entities = result.scalars().all()

                return [EntitySummary.model_validate(e) for e in entities]

        except Exception as e:
            logger.error(
                "Failed to list entities",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Build query with name search
                search_pattern = f"%{search_query}%"
                stmt = select(EntitiesTable).where(
                    EntitiesTable.user_id == user_id,
                    EntitiesTable.name.ilike(search_pattern)
                )

                # Apply optional filters
                if entity_type:
                    stmt = stmt.where(EntitiesTable.entity_type == entity_type.value)

                if tags:
                    stmt = stmt.where(EntitiesTable.tags.overlap(tags))

                # Order by creation date (newest first) and limit
                stmt = stmt.order_by(EntitiesTable.created_at.desc()).limit(limit)

                result = await session.execute(stmt)
                entities = result.scalars().all()

                logger.info("Entity search completed", extra={
                    "user_id": str(user_id),
                    "query": search_query,
                    "results_count": len(entities)
                })

                return [EntitySummary.model_validate(e) for e in entities]

        except Exception as e:
            logger.error(
                "Failed to search entities",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "query": search_query,
                    "error": str(e)
                }
            )
            raise

    async def update_entity(
        self,
        user_id: UUID,
        entity_id: int,
        entity_data: EntityUpdate
    ) -> Entity:
        """Update entity (PATCH semantics)

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Fetch existing entity
                stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )

                result = await session.execute(stmt)
                entity_table = result.scalar_one_or_none()

                if not entity_table:
                    raise NotFoundError(f"Entity {entity_id} not found")

                # Update only provided fields (PATCH)
                update_data = entity_data.model_dump(exclude_unset=True)

                # Convert EntityType enum to string if provided
                if "entity_type" in update_data and update_data["entity_type"]:
                    update_data["entity_type"] = update_data["entity_type"].value

                for field, value in update_data.items():
                    setattr(entity_table, field, value)

                # Update timestamp
                entity_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(entity_table)

                return Entity.model_validate(entity_table)

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update entity {entity_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "error": str(e)
                }
            )
            raise

    async def delete_entity(
        self,
        user_id: UUID,
        entity_id: int
    ) -> bool:
        """Delete entity (cascade removes associations and relationships)

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Check ownership and get entity
                stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )

                result = await session.execute(stmt)
                entity_table = result.scalar_one_or_none()

                if not entity_table:
                    return False

                await session.delete(entity_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete entity {entity_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "error": str(e)
                }
            )
            raise

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
            True if linked (or already linked), False if entity or memory not found

        Raises:
            NotFoundError: If entity or memory not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify entity exists and is owned by user
                entity_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )
                entity_result = await session.execute(entity_stmt)
                entity_table = entity_result.scalar_one_or_none()

                if not entity_table:
                    raise NotFoundError(f"Entity {entity_id} not found")

                # Verify memory exists and is owned by user
                memory_stmt = select(MemoryTable).where(
                    MemoryTable.id == memory_id,
                    MemoryTable.user_id == user_id
                )
                memory_result = await session.execute(memory_stmt)
                memory_table = memory_result.scalar_one_or_none()

                if not memory_table:
                    raise NotFoundError(f"Memory {memory_id} not found")

                # Load the entities relationship on the memory
                await session.refresh(memory_table, ["entities"])

                # Add entity to memory's entities (if not already linked)
                if entity_table not in memory_table.entities:
                    memory_table.entities.append(entity_table)
                    await session.commit()

                return True

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to link entity {entity_id} to memory {memory_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "memory_id": memory_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify entity exists and is owned by user
                entity_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )
                entity_result = await session.execute(entity_stmt)
                entity_table = entity_result.scalar_one_or_none()

                if not entity_table:
                    return False

                # Verify memory exists and is owned by user
                memory_stmt = select(MemoryTable).where(
                    MemoryTable.id == memory_id,
                    MemoryTable.user_id == user_id
                )
                memory_result = await session.execute(memory_stmt)
                memory_table = memory_result.scalar_one_or_none()

                if not memory_table:
                    return False

                # Load the entities relationship on the memory
                await session.refresh(memory_table, ["entities"])

                # Remove entity from memory's entities (if linked)
                if entity_table in memory_table.entities:
                    memory_table.entities.remove(entity_table)
                    await session.commit()
                    return True

                return False

        except Exception as e:
            logger.error(
                f"Failed to unlink entity {entity_id} from memory {memory_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "memory_id": memory_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify source entity exists and is owned by user
                source_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == relationship_data.source_entity_id,
                    EntitiesTable.user_id == user_id
                )
                source_result = await session.execute(source_stmt)
                source_entity = source_result.scalar_one_or_none()

                if not source_entity:
                    raise NotFoundError(f"Source entity {relationship_data.source_entity_id} not found")

                # Verify target entity exists and is owned by user
                target_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == relationship_data.target_entity_id,
                    EntitiesTable.user_id == user_id
                )
                target_result = await session.execute(target_stmt)
                target_entity = target_result.scalar_one_or_none()

                if not target_entity:
                    raise NotFoundError(f"Target entity {relationship_data.target_entity_id} not found")

                # Create ORM model from Pydantic
                relationship_table = EntityRelationshipsTable(
                    user_id=user_id,
                    source_entity_id=relationship_data.source_entity_id,
                    target_entity_id=relationship_data.target_entity_id,
                    relationship_type=relationship_data.relationship_type,
                    strength=relationship_data.strength,
                    confidence=relationship_data.confidence,
                    relationship_metadata=relationship_data.metadata or {}
                )

                session.add(relationship_table)
                await session.commit()
                await session.refresh(relationship_table)

                # Convert ORM to Pydantic (manually map relationship_metadata -> metadata)
                return EntityRelationship(
                    id=relationship_table.id,
                    source_entity_id=relationship_table.source_entity_id,
                    target_entity_id=relationship_table.target_entity_id,
                    relationship_type=relationship_table.relationship_type,
                    strength=relationship_table.strength,
                    confidence=relationship_table.confidence,
                    metadata=relationship_table.relationship_metadata,
                    created_at=relationship_table.created_at,
                    updated_at=relationship_table.updated_at
                )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create entity relationship",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Verify entity exists and is owned by user
                entity_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )
                entity_result = await session.execute(entity_stmt)
                entity_table = entity_result.scalar_one_or_none()

                if not entity_table:
                    raise NotFoundError(f"Entity {entity_id} not found")

                # Build query based on direction
                if direction == "outgoing":
                    stmt = select(EntityRelationshipsTable).where(
                        EntityRelationshipsTable.source_entity_id == entity_id,
                        EntityRelationshipsTable.user_id == user_id
                    )
                elif direction == "incoming":
                    stmt = select(EntityRelationshipsTable).where(
                        EntityRelationshipsTable.target_entity_id == entity_id,
                        EntityRelationshipsTable.user_id == user_id
                    )
                else:
                    # Both directions
                    stmt = select(EntityRelationshipsTable).where(
                        and_(
                            (EntityRelationshipsTable.source_entity_id == entity_id) |
                            (EntityRelationshipsTable.target_entity_id == entity_id),
                            EntityRelationshipsTable.user_id == user_id
                        )
                    )

                # Filter by relationship type if provided
                if relationship_type:
                    stmt = stmt.where(EntityRelationshipsTable.relationship_type == relationship_type)

                # Order by creation date (newest first)
                stmt = stmt.order_by(EntityRelationshipsTable.created_at.desc())

                result = await session.execute(stmt)
                relationships = result.scalars().all()

                # Convert ORM to Pydantic (manually map relationship_metadata -> metadata)
                return [
                    EntityRelationship(
                        id=r.id,
                        source_entity_id=r.source_entity_id,
                        target_entity_id=r.target_entity_id,
                        relationship_type=r.relationship_type,
                        strength=r.strength,
                        confidence=r.confidence,
                        metadata=r.relationship_metadata,
                        created_at=r.created_at,
                        updated_at=r.updated_at
                    )
                    for r in relationships
                ]

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get relationships for entity {entity_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Fetch existing relationship
                stmt = select(EntityRelationshipsTable).where(
                    EntityRelationshipsTable.id == relationship_id,
                    EntityRelationshipsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                relationship_table = result.scalar_one_or_none()

                if not relationship_table:
                    raise NotFoundError(f"Entity relationship {relationship_id} not found")

                # Update only provided fields (PATCH)
                update_data = relationship_data.model_dump(exclude_unset=True)

                # Map metadata field to relationship_metadata for ORM
                if 'metadata' in update_data:
                    update_data['relationship_metadata'] = update_data.pop('metadata')

                for field, value in update_data.items():
                    setattr(relationship_table, field, value)

                # Update timestamp
                relationship_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(relationship_table)

                # Convert ORM to Pydantic (manually map relationship_metadata -> metadata)
                return EntityRelationship(
                    id=relationship_table.id,
                    source_entity_id=relationship_table.source_entity_id,
                    target_entity_id=relationship_table.target_entity_id,
                    relationship_type=relationship_table.relationship_type,
                    strength=relationship_table.strength,
                    confidence=relationship_table.confidence,
                    metadata=relationship_table.relationship_metadata,
                    created_at=relationship_table.created_at,
                    updated_at=relationship_table.updated_at
                )

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update entity relationship {relationship_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "relationship_id": relationship_id,
                    "error": str(e)
                }
            )
            raise

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
        try:
            async with self.db_adapter.session(user_id) as session:
                # Check ownership and get relationship
                stmt = select(EntityRelationshipsTable).where(
                    EntityRelationshipsTable.id == relationship_id,
                    EntityRelationshipsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                relationship_table = result.scalar_one_or_none()

                if not relationship_table:
                    return False

                await session.delete(relationship_table)
                await session.commit()

                return True

        except Exception as e:
            logger.error(
                f"Failed to delete entity relationship {relationship_id}",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "relationship_id": relationship_id,
                    "error": str(e)
                }
            )
            raise
