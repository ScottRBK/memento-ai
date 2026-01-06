"""
PostgreSQL repository for Entity and EntityRelationship data access operations
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.repositories.postgres.postgres_tables import (
    EntitiesTable,
    EntityRelationshipsTable,
    MemoryTable,
    ProjectsTable,
    memory_entity_association,
    entity_project_association
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
                    aka=entity_data.aka
                )

                # Handle project associations (many-to-many)
                if entity_data.project_ids:
                    # Fetch project objects for the provided IDs
                    projects_stmt = select(ProjectsTable).where(
                        ProjectsTable.id.in_(entity_data.project_ids),
                        ProjectsTable.user_id == user_id
                    )
                    projects_result = await session.execute(projects_stmt)
                    projects = projects_result.scalars().all()

                    # Assign projects to the entity
                    entity_table.projects = list(projects)

                session.add(entity_table)
                await session.commit()
                await session.refresh(entity_table, ["projects"])

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
                # Query with ownership check and eager load projects
                stmt = select(EntitiesTable).options(
                    selectinload(EntitiesTable.projects)
                ).where(
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
        project_ids: List[int] | None = None,
        entity_type: EntityType | None = None,
        tags: List[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[List[EntitySummary], int]:
        """List entities with optional filtering and pagination

        Args:
            user_id: User ID for ownership filtering
            project_ids: Optional filter by project IDs (returns entities linked to ANY of these projects)
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY of these tags)
            limit: Maximum number of entities to return (default 20)
            offset: Number of entities to skip (default 0)

        Returns:
            Tuple of (entities, total_count) where:
            - entities: List of EntitySummary (lightweight, excludes notes)
            - total_count: Total matching entities before pagination
        """
        from sqlalchemy import func

        try:
            async with self.db_adapter.session(user_id) as session:
                # Build base conditions
                conditions = [EntitiesTable.user_id == user_id]

                if entity_type:
                    conditions.append(EntitiesTable.entity_type == entity_type.value)

                if tags:
                    # GIN array overlap search - finds entities with ANY of the provided tags
                    conditions.append(EntitiesTable.tags.overlap(tags))

                # Build main query with filters and eager load projects
                stmt = select(EntitiesTable).options(
                    selectinload(EntitiesTable.projects)
                ).where(*conditions)

                if project_ids is not None:
                    # Filter entities that have any of the specified project IDs
                    # Use join to the association table
                    stmt = stmt.join(EntitiesTable.projects).where(
                        ProjectsTable.id.in_(project_ids)
                    )

                # Order by creation date (newest first), then by ID for deterministic ordering
                stmt = stmt.order_by(
                    EntitiesTable.created_at.desc(),
                    EntitiesTable.id.desc()
                )

                # Apply pagination
                stmt = stmt.offset(offset).limit(limit)

                # Build count query with same conditions
                count_stmt = select(func.count(func.distinct(EntitiesTable.id))).where(*conditions)
                if project_ids is not None:
                    count_stmt = count_stmt.join(EntitiesTable.projects).where(
                        ProjectsTable.id.in_(project_ids)
                    )

                # Execute count query first
                total = await session.scalar(count_stmt)

                # Execute main query
                result = await session.execute(stmt)
                entities = result.unique().scalars().all()

                logger.info(
                    "Listed entities",
                    extra={
                        "user_id": str(user_id),
                        "count": len(entities),
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "project_filtered": project_ids is not None,
                        "entity_type": entity_type.value if entity_type else None,
                        "tags_filter": tags
                    }
                )

                return [EntitySummary.model_validate(e) for e in entities], total or 0

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
                # Build query with name + AKA search
                search_pattern = f"%{search_query}%"
                stmt = select(EntitiesTable).where(
                    EntitiesTable.user_id == user_id,
                    or_(
                        EntitiesTable.name.ilike(search_pattern),
                        # Search in AKA array - convert to string and search
                        func.array_to_string(EntitiesTable.aka, ' ').ilike(search_pattern)
                    )
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
                # Fetch existing entity with projects loaded
                stmt = select(EntitiesTable).options(
                    selectinload(EntitiesTable.projects)
                ).where(
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

                # Handle project_ids separately (many-to-many relationship)
                project_ids = update_data.pop("project_ids", None)

                for field, value in update_data.items():
                    setattr(entity_table, field, value)

                # Update project associations if provided
                if project_ids is not None:
                    # Fetch project objects for the provided IDs
                    projects_stmt = select(ProjectsTable).where(
                        ProjectsTable.id.in_(project_ids),
                        ProjectsTable.user_id == user_id
                    )
                    projects_result = await session.execute(projects_stmt)
                    projects = projects_result.scalars().all()

                    # Replace existing projects with new ones
                    entity_table.projects = list(projects)

                # Update timestamp
                entity_table.updated_at = datetime.now(timezone.utc)

                await session.commit()
                await session.refresh(entity_table, ["projects"])

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

    # Graph visualization operations

    async def get_all_entity_relationships(
        self,
        user_id: UUID
    ) -> List[EntityRelationship]:
        """Get all entity relationships for a user (for graph visualization)

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of all EntityRelationship owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                stmt = select(EntityRelationshipsTable).where(
                    EntityRelationshipsTable.user_id == user_id
                ).order_by(EntityRelationshipsTable.created_at.desc())

                result = await session.execute(stmt)
                relationships = result.scalars().all()

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

        except Exception as e:
            logger.error(
                "Failed to get all entity relationships",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_all_entity_memory_links(
        self,
        user_id: UUID
    ) -> List[tuple[int, int]]:
        """Get all entity-memory associations for a user (for graph visualization)

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of (entity_id, memory_id) tuples representing all links
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Query the association table with ownership verification
                stmt = select(
                    memory_entity_association.c.entity_id,
                    memory_entity_association.c.memory_id
                ).select_from(
                    memory_entity_association
                ).join(
                    EntitiesTable,
                    EntitiesTable.id == memory_entity_association.c.entity_id
                ).join(
                    MemoryTable,
                    MemoryTable.id == memory_entity_association.c.memory_id
                ).where(
                    EntitiesTable.user_id == user_id,
                    MemoryTable.user_id == user_id
                )

                result = await session.execute(stmt)
                return [(row.entity_id, row.memory_id) for row in result]

        except Exception as e:
            logger.error(
                "Failed to get all entity-memory links",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_all_entity_project_links(
        self,
        user_id: UUID
    ) -> List[tuple[int, int]]:
        """Get all entity-project associations for a user (for graph visualization)

        Args:
            user_id: User ID for ownership filtering

        Returns:
            List of (entity_id, project_id) tuples representing all links
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # Query the association table with ownership verification
                stmt = select(
                    entity_project_association.c.entity_id,
                    entity_project_association.c.project_id
                ).select_from(
                    entity_project_association
                ).join(
                    EntitiesTable,
                    EntitiesTable.id == entity_project_association.c.entity_id
                ).join(
                    ProjectsTable,
                    ProjectsTable.id == entity_project_association.c.project_id
                ).where(
                    EntitiesTable.user_id == user_id,
                    ProjectsTable.user_id == user_id
                )

                result = await session.execute(stmt)
                return [(row.entity_id, row.project_id) for row in result]

        except Exception as e:
            logger.error(
                "Failed to get all entity-project links",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "error": str(e)
                }
            )
            raise

    async def get_entity_memories(
        self,
        user_id: UUID,
        entity_id: int
    ) -> List[int]:
        """Get all memory IDs linked to a specific entity

        Args:
            user_id: User ID for ownership verification
            entity_id: Entity ID to get memories for

        Returns:
            List of memory IDs linked to this entity

        Raises:
            NotFoundError: If entity not found or not owned by user
        """
        try:
            async with self.db_adapter.session(user_id) as session:
                # First verify the entity exists and is owned by user
                entity_stmt = select(EntitiesTable).where(
                    EntitiesTable.id == entity_id,
                    EntitiesTable.user_id == user_id
                )
                entity_result = await session.execute(entity_stmt)
                entity = entity_result.scalar_one_or_none()

                if not entity:
                    raise NotFoundError(f"Entity {entity_id} not found")

                # Query the association table for memory IDs linked to this entity
                stmt = select(
                    memory_entity_association.c.memory_id
                ).select_from(
                    memory_entity_association
                ).join(
                    MemoryTable,
                    MemoryTable.id == memory_entity_association.c.memory_id
                ).where(
                    memory_entity_association.c.entity_id == entity_id,
                    MemoryTable.user_id == user_id
                )

                result = await session.execute(stmt)
                return [row.memory_id for row in result]

        except NotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Failed to get entity memories",
                exc_info=True,
                extra={
                    "user_id": str(user_id),
                    "entity_id": entity_id,
                    "error": str(e)
                }
            )
            raise
