"""
MCP Entity tools - FastMCP tool definitions for entity and entity relationship operations
"""
from typing import List, Dict, Any

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.models.entity_models import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntityRelationship,
    EntityRelationshipCreate,
    EntityRelationshipUpdate,
    EntityType
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import filter_none_values

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register entity tools - services accessed via context at call time"""

    # Entity CRUD tools

    @mcp.tool()
    async def create_entity(
        name: str,
        entity_type: str,
        ctx: Context,
        custom_type: str = None,
        notes: str = None,
        tags: List[str] = None,
        project_id: int = None,
    ) -> Entity:
        """
        Create entity representing a real-world entity (organization, individual, team, device).

        WHAT: Stores information about real-world entities that can be referenced by memories
        and connected through relationships to form a knowledge graph. Entities represent
        people, organizations, teams, devices, or custom entity types.

        WHEN: When tracking information about entities that appear in your work:
        - People (teammates, clients, experts)
        - Organizations (companies, teams, departments)
        - Devices (servers, workstations, infrastructure)
        - Custom entities specific to your domain

        BEHAVIOR: Creates entity with provided details. Can be associated with a project
        immediately via project_id. Returns complete entity with generated ID. To link to
        memories, use link_entity_to_memory. To create relationships with other entities,
        use create_entity_relationship.

        NOT-USE: For abstract concepts (use memories), code snippets (use code artifacts),
        or documentation (use documents). Entities are for concrete, identifiable entities.

        EXAMPLES:
        create_entity(
            name="Sarah Chen",
            entity_type="Individual",
            notes="Lead backend developer specializing in microservices architecture",
            tags=["engineering", "backend", "microservices"]
        )

        create_entity(
            name="TechFlow Systems",
            entity_type="Organization",
            notes="Cloud infrastructure and managed services provider",
            tags=["cloud", "infrastructure", "saas"]
        )

        create_entity(
            name="Cache Server 01",
            entity_type="Device",
            notes="Redis cluster primary node for session management",
            tags=["cache", "redis", "infrastructure"]
        )

        create_entity(
            name="Message Queue",
            entity_type="Other",
            custom_type="Middleware",
            notes="RabbitMQ message broker for event-driven workflows",
            tags=["messaging", "rabbitmq", "middleware"]
        )

        Args:
            name: Entity name (max 200 chars) - searchable identifier
            entity_type: Entity type: Organization, Individual, Team, Device, or Other
            custom_type: Required when entity_type is "Other" - specify custom type
            notes: Additional context about this entity (bio, description, purpose)
            tags: Optional tags for discovery and categorization (max 10)
            project_id: Optional project ID for immediate association
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete Entity with ID, timestamps, and metadata
        """

        logger.info("MCP Tool Called -> create_entity", extra={
            "entity_name": name[:50],
            "entity_type": entity_type
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_data = EntityCreate(
                name=name,
                entity_type=EntityType(entity_type.title()),
                custom_type=custom_type,
                notes=notes,
                tags=tags or [],
                project_id=project_id
            )
        except (ValidationError, ValueError) as e:
            raise ToolError(f"Invalid entity data: {e}")

        try:
            entity_service = ctx.fastmcp.entity_service
            entity = await entity_service.create_entity(
                user_id=user.id,
                entity_data=entity_data
            )

            return entity

        except Exception as e:
            logger.error("Failed to create entity", exc_info=True)
            raise ToolError(f"Failed to create entity: {str(e)}")

    @mcp.tool()
    async def get_entity(
        entity_id: int,
        ctx: Context
    ) -> Entity:
        """
        Retrieve entity by ID with complete details.

        WHEN: You need the full entity information for a specific entity.
        Common after listing entities or when a memory references an entity ID.

        BEHAVIOR: Returns complete entity including notes and metadata.
        Ownership verified automatically.

        NOT-USE: For browsing multiple entities (use list_entities).

        Args:
            entity_id: Unique entity ID
            ctx: Context (automatically injected)

        Returns:
            Complete Entity with name, type, notes, tags, timestamps

        Raises:
            ToolError: If entity not found or not owned by user
        """

        logger.info("MCP Tool Called -> get_entity", extra={
            "entity_id": entity_id
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            entity = await entity_service.get_entity(
                user_id=user.id,
                entity_id=entity_id
            )

            return entity

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to get entity", exc_info=True)
            raise ToolError(f"Failed to get entity: {str(e)}")

    @mcp.tool()
    async def list_entities(
        ctx: Context,
        project_id: int = None,
        entity_type: str = None,
        tags: List[str] = None
    ) -> dict:
        """
        List entities with optional filtering.

        WHEN: Browsing entities, filtering by project/type/tags, or discovering
        available entities before linking to memories or creating relationships.

        BEHAVIOR: Returns lightweight entity summaries (excludes notes to save tokens).
        Results sorted by creation date (newest first). Use get_entity for full details.

        FILTERS:
        - project_id: Show only entities in specific project
        - entity_type: Filter by type (Organization, Individual, Team, Device, Other)
        - tags: Show entities with ANY of these tags (OR logic)

        Args:
            project_id: Optional filter by project
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY matching tag)
            ctx: Context (automatically injected)

        Returns:
            List of EntitySummary (lightweight, excludes notes)
        """

        logger.info("MCP Tool Called -> list_entities", extra={
            "project_id": project_id,
            "entity_type": entity_type,
            "tags": tags
        })

        user = await get_user_from_auth(ctx)

        try:
            # Convert entity_type string to enum if provided
            entity_type_enum = EntityType(entity_type.title()) if entity_type else None

            entity_service = ctx.fastmcp.entity_service
            entities = await entity_service.list_entities(
                user_id=user.id,
                project_id=project_id,
                entity_type=entity_type_enum,
                tags=tags
            )

            return {
                "entities": entities,
                "total_count": len(entities),
                "filters": {
                    "project_id": project_id,
                    "entity_type": entity_type,
                    "tags": tags
                }
            }

        except ValueError as e:
            raise ToolError(f"Invalid entity_type: {e}")
        except Exception as e:
            logger.error("Failed to list entities", exc_info=True)
            raise ToolError(f"Failed to list entities: {str(e)}")

    @mcp.tool()
    async def search_entities(
        query: str,
        ctx: Context,
        entity_type: str = None,
        tags: List[str] = None,
        limit: int = 20
    ) -> dict:
        """
        Search entities by name using text matching.

        WHEN: Looking for specific entities by name. Examples:
        - "Find entities named Sarah"
        - "Search for organizations containing 'Tech'"
        - "Find all entities with 'server' in name"

        BEHAVIOR: Case-insensitive text search on entity name field. Returns lightweight
        entity summaries (excludes notes to save tokens). Results sorted by creation date
        (newest first). Use get_entity for full details including notes.

        NOT-USE: Listing all entities (use list_entities), semantic/meaning-based search
        (not available for entities), searching memories (use query_memory).

        FILTERS (optional):
        - entity_type: Filter by type (Organization, Individual, Team, Device, Other)
        - tags: Show entities with ANY of these tags (OR logic)
        - limit: Maximum results (1-100, default 20)

        Args:
            query: Text to search for in entity name (required)
            entity_type: Optional filter by entity type
            tags: Optional filter by tags (returns entities with ANY matching tag)
            limit: Maximum number of results (1-100, default 20)
            ctx: Context (automatically injected)

        Returns:
            Dict with entities list, total_count, and search_query
        """

        logger.info("MCP Tool Called -> search_entities", extra={
            "query": query,
            "entity_type": entity_type,
            "tags": tags,
            "limit": limit
        })

        user = await get_user_from_auth(ctx)

        try:
            # Convert entity_type string to enum if provided
            entity_type_enum = EntityType(entity_type.title()) if entity_type else None

            # Clamp limit to reasonable range
            limit = max(1, min(limit, 100))

            entity_service = ctx.fastmcp.entity_service
            entities = await entity_service.search_entities(
                user_id=user.id,
                search_query=query,
                entity_type=entity_type_enum,
                tags=tags,
                limit=limit
            )

            return {
                "entities": entities,
                "total_count": len(entities),
                "search_query": query,
                "filters": {
                    "entity_type": entity_type,
                    "tags": tags,
                    "limit": limit
                }
            }

        except ValueError as e:
            raise ToolError(f"Invalid entity_type: {e}")
        except Exception as e:
            logger.error("Failed to search entities", exc_info=True)
            raise ToolError(f"Failed to search entities: {str(e)}")

    @mcp.tool()
    async def update_entity(
        entity_id: int,
        ctx: Context,
        name: str = None,
        entity_type: str = None,
        custom_type: str = None,
        notes: str = None,
        tags: List[str] = None,
        project_id: int = None
    ) -> Entity:
        """
        Update existing entity (PATCH semantics - only provided fields changed).

        WHEN: Modifying entity information after creation. Common scenarios:
        - Adding/updating notes
        - Changing tags
        - Updating entity type
        - Moving to different project

        BEHAVIOR: Only provided arguments are updated. Null/omitted arguments leave
        the field unchanged. Empty string ("") clears optional text fields.
        Returns updated entity with new timestamps.

        Args:
            entity_id: Entity ID to update
            name: New name (unchanged if omitted)
            entity_type: New type (unchanged if omitted)
            custom_type: New custom type when entity_type is "Other"
            notes: New notes (unchanged if omitted, clears if empty string)
            tags: New tags (unchanged if omitted, replaces existing if provided)
            project_id: New project association (unchanged if omitted)
            ctx: Context (automatically injected)

        Returns:
            Updated Entity with new timestamps

        Raises:
            ToolError: If entity not found or validation fails
        """

        logger.info("MCP Tool Called -> update_entity", extra={
            "entity_id": entity_id
        })

        user = await get_user_from_auth(ctx)

        # Build update dict with only provided values
        update_dict = filter_none_values(
            name=name,
            entity_type=EntityType(entity_type.title()) if entity_type else None,
            custom_type=custom_type,
            notes=notes,
            tags=tags,
            project_id=project_id
        )

        if not update_dict:
            raise ToolError("No fields provided to update")

        try:
            entity_data = EntityUpdate(**update_dict)
        except (ValidationError, ValueError) as e:
            raise ToolError(f"Invalid update data: {e}")

        try:
            entity_service = ctx.fastmcp.entity_service
            entity = await entity_service.update_entity(
                user_id=user.id,
                entity_id=entity_id,
                entity_data=entity_data
            )

            return entity

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to update entity", exc_info=True)
            raise ToolError(f"Failed to update entity: {str(e)}")

    @mcp.tool()
    async def delete_entity(
        entity_id: int,
        ctx: Context
    ) -> dict:
        """
        Delete entity (cascade removes memory links and relationships).

        WHEN: Removing obsolete or incorrect entities. Use carefully - this is permanent.

        BEHAVIOR: Removes entity and all its relationships (both incoming and outgoing).
        Memory links are removed but memories themselves are preserved. Cannot be undone.

        Args:
            entity_id: Entity ID to delete
            ctx: Context (automatically injected)

        Returns:
            Success confirmation with deleted entity ID

        Raises:
            ToolError: If deletion fails
        """

        logger.info("MCP Tool Called -> delete_entity", extra={
            "entity_id": entity_id
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            success = await entity_service.delete_entity(
                user_id=user.id,
                entity_id=entity_id
            )

            if not success:
                raise ToolError(f"Entity {entity_id} not found")

            return {"deleted_id": entity_id}

        except Exception as e:
            logger.error("Failed to delete entity", exc_info=True)
            raise ToolError(f"Failed to delete entity: {str(e)}")

    # Entity-Memory linking tools

    @mcp.tool()
    async def link_entity_to_memory(
        entity_id: int,
        memory_id: int,
        ctx: Context
    ) -> dict:
        """
        Link entity to memory (establishes reference relationship).

        WHEN: When a memory mentions or relates to an entity. Creates bidirectional
        link so the entity can be discovered from the memory and vice versa.

        BEHAVIOR: Creates association between entity and memory. Idempotent - safe
        to call multiple times (won't create duplicates). Both entity and memory
        must exist and be owned by the user.

        EXAMPLES:
        # After creating memory about a technical decision:
        link_entity_to_memory(entity_id=5, memory_id=123)  # Link to decision maker

        # After creating memory about a system issue:
        link_entity_to_memory(entity_id=12, memory_id=456)  # Link to affected server

        Args:
            entity_id: Entity ID to link
            memory_id: Memory ID to link
            ctx: Context (automatically injected)

        Returns:
            True if linked successfully (or already linked)

        Raises:
            ToolError: If entity or memory not found or not owned by user
        """

        logger.info("MCP Tool Called -> link_entity_to_memory", extra={
            "entity_id": entity_id,
            "memory_id": memory_id
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            success = await entity_service.link_entity_to_memory(
                user_id=user.id,
                entity_id=entity_id,
                memory_id=memory_id
            )

            return {"success": success}

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to link entity to memory", exc_info=True)
            raise ToolError(f"Failed to link entity to memory: {str(e)}")

    @mcp.tool()
    async def unlink_entity_from_memory(
        entity_id: int,
        memory_id: int,
        ctx: Context
    ) -> dict:
        """
        Unlink entity from memory (removes reference relationship).

        WHEN: When an entity-memory link is no longer relevant or was created in error.

        BEHAVIOR: Removes association between entity and memory. Safe to call even
        if link doesn't exist (returns False). Entity and memory remain intact.

        Args:
            entity_id: Entity ID to unlink
            memory_id: Memory ID to unlink
            ctx: Context (automatically injected)

        Returns:
            True if link was removed, False if link didn't exist

        Raises:
            ToolError: If unlinking fails
        """

        logger.info("MCP Tool Called -> unlink_entity_from_memory", extra={
            "entity_id": entity_id,
            "memory_id": memory_id
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            success = await entity_service.unlink_entity_from_memory(
                user_id=user.id,
                entity_id=entity_id,
                memory_id=memory_id
            )

            return {"success": success}

        except Exception as e:
            logger.error("Failed to unlink entity from memory", exc_info=True)
            raise ToolError(f"Failed to unlink entity from memory: {str(e)}")

    # Entity Relationship tools

    @mcp.tool()
    async def create_entity_relationship(
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        ctx: Context,
        strength: float = None,
        confidence: float = None,
        metadata: Dict[str, Any] = None
    ) -> EntityRelationship:
        """
        Create typed relationship between two entities (knowledge graph edge).

        WHAT: Establishes directed, typed relationship with optional strength, confidence,
        and metadata. Forms knowledge graph showing how entities relate to each other.

        WHEN: When you want to capture relationships between entities:
        - Employment: person → organization ("works_at")
        - Ownership: person → device ("owns")
        - Management: person → person ("manages")
        - Membership: person → team ("member_of")
        - Dependencies: system → system ("depends_on")

        BEHAVIOR: Creates weighted, directed edge from source to target entity.
        Strength (0.0-1.0) indicates relationship significance. Confidence (0.0-1.0)
        indicates certainty. Metadata can store additional context like source,
        dates, roles, etc.

        EXAMPLES:
        create_entity_relationship(
            source_entity_id=5,  # Sarah Chen
            target_entity_id=12, # TechFlow Systems
            relationship_type="works_at",
            strength=0.9,
            confidence=0.95,
            metadata={"role": "Lead Developer", "start_date": "2024-03-01"}
        )

        create_entity_relationship(
            source_entity_id=8,  # Payment Service
            target_entity_id=15, # Cache Server 01
            relationship_type="depends_on",
            strength=1.0,
            confidence=1.0,
            metadata={"criticality": "high", "last_verified": "2025-11-13"}
        )

        Args:
            source_entity_id: Source entity ID (the "from" entity)
            target_entity_id: Target entity ID (the "to" entity)
            relationship_type: Type of relationship (e.g., "works_at", "owns", "manages")
            strength: Optional relationship strength (0.0-1.0)
            confidence: Optional confidence score (0.0-1.0)
            metadata: Optional dict with additional context (source, dates, etc.)
            ctx: Context (automatically injected)

        Returns:
            Created EntityRelationship with ID and timestamps

        Raises:
            ToolError: If entities not found, validation fails, or relationship exists
        """

        logger.info("MCP Tool Called -> create_entity_relationship", extra={
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
            "relationship_type": relationship_type
        })

        user = await get_user_from_auth(ctx)

        try:
            relationship_data = EntityRelationshipCreate(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                relationship_type=relationship_type,
                strength=strength,
                confidence=confidence,
                metadata=metadata
            )
        except ValidationError as e:
            raise ToolError(f"Invalid relationship data: {e}")

        try:
            entity_service = ctx.fastmcp.entity_service
            relationship = await entity_service.create_entity_relationship(
                user_id=user.id,
                relationship_data=relationship_data
            )

            return relationship

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to create entity relationship", exc_info=True)
            raise ToolError(f"Failed to create entity relationship: {str(e)}")

    @mcp.tool()
    async def get_entity_relationships(
        entity_id: int,
        ctx: Context,
        direction: str = None,
        relationship_type: str = None
    ) -> dict:
        """
        Get relationships for an entity (knowledge graph edges).

        WHEN: Exploring entity connections, analyzing network structure, or
        understanding how entities relate to each other.

        BEHAVIOR: Returns relationships involving the entity. Can filter by direction
        (outgoing/incoming/both) and relationship type. Results sorted by creation
        date (newest first).

        FILTERS:
        - direction: "outgoing" (where entity is source), "incoming" (where entity
          is target), or null (both directions)
        - relationship_type: Filter by specific type (e.g., "works_at")

        EXAMPLES:
        # Get all relationships for a person
        get_entity_relationships(entity_id=5)

        # Get only employment relationships
        get_entity_relationships(entity_id=5, relationship_type="works_at")

        # Get who manages this person
        get_entity_relationships(entity_id=5, direction="incoming", relationship_type="manages")

        Args:
            entity_id: Entity ID to get relationships for
            direction: Optional filter: "outgoing", "incoming", or null (both)
            relationship_type: Optional filter by relationship type
            ctx: Context (automatically injected)

        Returns:
            List of EntityRelationship sorted by creation date

        Raises:
            ToolError: If entity not found or query fails
        """

        logger.info("MCP Tool Called -> get_entity_relationships", extra={
            "entity_id": entity_id,
            "direction": direction,
            "relationship_type": relationship_type
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            relationships = await entity_service.get_entity_relationships(
                user_id=user.id,
                entity_id=entity_id,
                direction=direction,
                relationship_type=relationship_type
            )

            return {
                "relationships": relationships,
                "total_count": len(relationships),
                "filters": {
                    "entity_id": entity_id,
                    "direction": direction,
                    "relationship_type": relationship_type
                }
            }

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to get entity relationships", exc_info=True)
            raise ToolError(f"Failed to get entity relationships: {str(e)}")

    @mcp.tool()
    async def update_entity_relationship(
        relationship_id: int,
        ctx: Context,
        relationship_type: str = None,
        strength: float = None,
        confidence: float = None,
        metadata: Dict[str, Any] = None
    ) -> EntityRelationship:
        """
        Update entity relationship (PATCH semantics - only provided fields changed).

        WHEN: Refining relationship details after creation:
        - Updating strength/confidence based on new information
        - Adding metadata (verification dates, additional context)
        - Changing relationship type

        BEHAVIOR: Only provided arguments are updated. Null/omitted arguments leave
        the field unchanged. Returns updated relationship with new timestamps.

        Args:
            relationship_id: Relationship ID to update
            relationship_type: New type (unchanged if omitted)
            strength: New strength (unchanged if omitted)
            confidence: New confidence (unchanged if omitted)
            metadata: New metadata dict (unchanged if omitted, replaces if provided)
            ctx: Context (automatically injected)

        Returns:
            Updated EntityRelationship with new timestamps

        Raises:
            ToolError: If relationship not found or validation fails
        """

        logger.info("MCP Tool Called -> update_entity_relationship", extra={
            "relationship_id": relationship_id
        })

        user = await get_user_from_auth(ctx)

        # Build update dict with only provided values
        update_dict = filter_none_values(
            relationship_type=relationship_type,
            strength=strength,
            confidence=confidence,
            metadata=metadata
        )

        if not update_dict:
            raise ToolError("No fields provided to update")

        try:
            relationship_data = EntityRelationshipUpdate(**update_dict)
        except ValidationError as e:
            raise ToolError(f"Invalid update data: {e}")

        try:
            entity_service = ctx.fastmcp.entity_service
            relationship = await entity_service.update_entity_relationship(
                user_id=user.id,
                relationship_id=relationship_id,
                relationship_data=relationship_data
            )

            return relationship

        except NotFoundError as e:
            raise ToolError(str(e))
        except Exception as e:
            logger.error("Failed to update entity relationship", exc_info=True)
            raise ToolError(f"Failed to update entity relationship: {str(e)}")

    @mcp.tool()
    async def delete_entity_relationship(
        relationship_id: int,
        ctx: Context
    ) -> dict:
        """
        Delete entity relationship (removes knowledge graph edge).

        WHEN: Removing obsolete or incorrect relationships. Use carefully - this is permanent.

        BEHAVIOR: Removes relationship between entities. Entities remain intact.
        Cannot be undone.

        Args:
            relationship_id: Relationship ID to delete
            ctx: Context (automatically injected)

        Returns:
            Success confirmation with deleted relationship ID

        Raises:
            ToolError: If deletion fails
        """

        logger.info("MCP Tool Called -> delete_entity_relationship", extra={
            "relationship_id": relationship_id
        })

        user = await get_user_from_auth(ctx)

        try:
            entity_service = ctx.fastmcp.entity_service
            success = await entity_service.delete_entity_relationship(
                user_id=user.id,
                relationship_id=relationship_id
            )

            if not success:
                raise ToolError(f"Entity relationship {relationship_id} not found")

            return {"deleted_id": relationship_id}

        except Exception as e:
            logger.error("Failed to delete entity relationship", exc_info=True)
            raise ToolError(f"Failed to delete entity relationship: {str(e)}")
