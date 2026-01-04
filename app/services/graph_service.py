"""
Graph Service - Business logic for graph traversal and visualization

This service implements functionality for efficient graph visualization:
    - Subgraph traversal using recursive CTEs
    - Fetching full node data for memory and entity nodes
    - Building edges between nodes in the subgraph
"""
from typing import List, Set, Tuple
from uuid import UUID
import re

from app.config.logging_config import logging
from app.protocols.memory_protocol import MemoryRepository
from app.protocols.entity_protocol import EntityRepository
from app.models.graph_models import (
    SubgraphNode,
    SubgraphEdge,
    SubgraphMeta,
    SubgraphResponse,
)
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# Regex pattern for parsing node IDs
NODE_ID_PATTERN = re.compile(r'^(memory|entity)_(\d+)$')


class GraphService:
    """Service layer for graph traversal operations.

    Handles business logic for efficient subgraph extraction using
    recursive CTE queries. Coordinates between memory and entity
    repositories to build complete subgraph responses.
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        entity_repo: EntityRepository
    ):
        """Initialize with repository protocols.

        Args:
            memory_repo: Memory repository implementing the protocol
            entity_repo: Entity repository implementing the protocol
        """
        self.memory_repo = memory_repo
        self.entity_repo = entity_repo
        logger.info("Graph service initialized")

    @staticmethod
    def parse_node_id(node_id: str) -> Tuple[str, int]:
        """Parse node_id string into type and numeric ID.

        Args:
            node_id: Format 'memory_123' or 'entity_456'

        Returns:
            Tuple of (node_type, numeric_id)

        Raises:
            ValueError: If node_id format is invalid
        """
        match = NODE_ID_PATTERN.match(node_id)
        if not match:
            raise ValueError(
                f"Invalid node_id format: '{node_id}'. "
                "Expected 'memory_{{id}}' or 'entity_{{id}}'."
            )
        return match.group(1), int(match.group(2))

    async def get_subgraph(
        self,
        user_id: UUID,
        center_node_id: str,
        depth: int = 2,
        node_types: List[str] | None = None,
        max_nodes: int = 200
    ) -> SubgraphResponse:
        """Get subgraph centered on a node using recursive CTE traversal.

        Performs efficient graph traversal in a single database query,
        then fetches full node data and builds edges between nodes.

        Args:
            user_id: User ID for ownership filtering
            center_node_id: Format 'memory_123' or 'entity_456'
            depth: Traversal depth 1-3 (default 2, clamped)
            node_types: Filter to ['memory'], ['entity'], or both (default both)
            max_nodes: Safety limit (default 200, max 500)

        Returns:
            SubgraphResponse with nodes, edges, and metadata

        Raises:
            ValueError: If center_node_id format is invalid
            NotFoundError: If center node doesn't exist
        """
        # Parse and validate center node
        center_type, center_id = self.parse_node_id(center_node_id)

        # Validate center node exists
        await self._validate_center_node(user_id, center_type, center_id)

        # Clamp parameters
        depth = max(1, min(depth, 3))
        max_nodes = max(1, min(max_nodes, 500))

        # Determine which node types to include
        if node_types is None:
            node_types = ["memory", "entity"]
        include_memories = "memory" in node_types
        include_entities = "entity" in node_types

        logger.info(
            "Starting subgraph traversal",
            extra={
                "user_id": str(user_id),
                "center_node_id": center_node_id,
                "depth": depth,
                "node_types": node_types,
                "max_nodes": max_nodes,
            }
        )

        # Execute CTE query to get node IDs with depths
        raw_nodes, truncated = await self.memory_repo.get_subgraph_nodes(
            user_id=user_id,
            center_type=center_type,
            center_id=center_id,
            depth=depth,
            include_memories=include_memories,
            include_entities=include_entities,
            max_nodes=max_nodes,
        )

        # Separate node IDs by type
        memory_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "memory"]
        entity_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "entity"]

        # Build depth lookup
        depth_lookup = {
            (n["node_type"], n["node_id"]): n["depth"]
            for n in raw_nodes
        }

        # Fetch full node data
        nodes = await self._fetch_node_data(
            user_id, memory_ids, entity_ids, depth_lookup
        )

        # Fetch edges between nodes in the subgraph
        edges = await self._fetch_edges(
            user_id, memory_ids, entity_ids
        )

        # Build metadata
        memory_count = len([n for n in nodes if n.type == "memory"])
        entity_count = len([n for n in nodes if n.type == "entity"])
        memory_link_count = len([e for e in edges if e.type == "memory_link"])
        entity_relationship_count = len([e for e in edges if e.type == "entity_relationship"])
        entity_memory_count = len([e for e in edges if e.type == "entity_memory"])

        meta = SubgraphMeta(
            center_node_id=center_node_id,
            depth=depth,
            node_types=node_types,
            max_nodes=max_nodes,
            memory_count=memory_count,
            entity_count=entity_count,
            edge_count=len(edges),
            memory_link_count=memory_link_count,
            entity_relationship_count=entity_relationship_count,
            entity_memory_count=entity_memory_count,
            truncated=truncated,
        )

        logger.info(
            "Subgraph traversal completed",
            extra={
                "user_id": str(user_id),
                "center_node_id": center_node_id,
                "nodes_count": len(nodes),
                "edges_count": len(edges),
                "truncated": truncated,
            }
        )

        return SubgraphResponse(nodes=nodes, edges=edges, meta=meta)

    async def _validate_center_node(
        self,
        user_id: UUID,
        center_type: str,
        center_id: int
    ) -> None:
        """Validate that the center node exists.

        Raises:
            NotFoundError: If center node doesn't exist
        """
        if center_type == "memory":
            await self.memory_repo.get_memory_by_id(
                user_id=user_id,
                memory_id=center_id
            )
        else:  # entity
            entity = await self.entity_repo.get_entity_by_id(
                user_id=user_id,
                entity_id=center_id
            )
            if entity is None:
                raise NotFoundError(f"Entity {center_id} not found")

    async def _fetch_node_data(
        self,
        user_id: UUID,
        memory_ids: List[int],
        entity_ids: List[int],
        depth_lookup: dict
    ) -> List[SubgraphNode]:
        """Fetch full data for memory and entity nodes.

        Args:
            user_id: User ID for ownership
            memory_ids: List of memory IDs to fetch
            entity_ids: List of entity IDs to fetch
            depth_lookup: Dict mapping (type, id) to depth

        Returns:
            List of SubgraphNode with full data
        """
        nodes: List[SubgraphNode] = []

        # Fetch memories
        for memory_id in memory_ids:
            try:
                memory = await self.memory_repo.get_memory_by_id(
                    user_id=user_id,
                    memory_id=memory_id
                )
                nodes.append(SubgraphNode(
                    id=f"memory_{memory.id}",
                    type="memory",
                    depth=depth_lookup.get(("memory", memory_id), 0),
                    label=memory.title,
                    data={
                        "id": memory.id,
                        "title": memory.title,
                        "importance": memory.importance,
                        "tags": memory.tags,
                        "created_at": memory.created_at.isoformat() if memory.created_at else None,
                    }
                ))
            except NotFoundError:
                # Skip if memory was deleted during traversal
                logger.warning(f"Memory {memory_id} not found during fetch")
                continue

        # Fetch entities
        for entity_id in entity_ids:
            entity = await self.entity_repo.get_entity_by_id(
                user_id=user_id,
                entity_id=entity_id
            )
            if entity is None:
                # Skip if entity was deleted during traversal
                logger.warning(f"Entity {entity_id} not found during fetch")
                continue
            nodes.append(SubgraphNode(
                id=f"entity_{entity.id}",
                type="entity",
                depth=depth_lookup.get(("entity", entity_id), 0),
                label=entity.name,
                data={
                    "id": entity.id,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else entity.entity_type,
                    "created_at": entity.created_at.isoformat() if entity.created_at else None,
                }
            ))

        return nodes

    async def _fetch_edges(
        self,
        user_id: UUID,
        memory_ids: List[int],
        entity_ids: List[int]
    ) -> List[SubgraphEdge]:
        """Fetch all edges between nodes in the subgraph.

        Retrieves:
        - Memory-to-memory links
        - Entity-to-memory links
        - Entity-to-entity relationships

        Args:
            user_id: User ID for ownership
            memory_ids: List of memory IDs in subgraph
            entity_ids: List of entity IDs in subgraph

        Returns:
            List of SubgraphEdge
        """
        edges: List[SubgraphEdge] = []
        seen_edge_ids: Set[str] = set()

        memory_id_set = set(memory_ids)
        entity_id_set = set(entity_ids)

        # Fetch memory-to-memory edges
        if memory_ids:
            for memory_id in memory_ids:
                try:
                    memory = await self.memory_repo.get_memory_by_id(
                        user_id=user_id,
                        memory_id=memory_id
                    )
                    for linked_id in memory.linked_memory_ids:
                        if linked_id in memory_id_set:
                            # Canonical edge ID for deduplication
                            min_id = min(memory_id, linked_id)
                            max_id = max(memory_id, linked_id)
                            edge_id = f"memory_{min_id}_memory_{max_id}"

                            if edge_id not in seen_edge_ids:
                                seen_edge_ids.add(edge_id)
                                edges.append(SubgraphEdge(
                                    id=edge_id,
                                    source=f"memory_{memory_id}",
                                    target=f"memory_{linked_id}",
                                    type="memory_link",
                                ))
                except NotFoundError:
                    continue

        # Fetch entity-to-memory edges
        if entity_ids and memory_ids:
            entity_memory_links = await self.entity_repo.get_all_entity_memory_links(
                user_id=user_id
            )
            for entity_id, mem_id in entity_memory_links:
                if entity_id in entity_id_set and mem_id in memory_id_set:
                    edge_id = f"entity_{entity_id}_memory_{mem_id}"
                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append(SubgraphEdge(
                            id=edge_id,
                            source=f"entity_{entity_id}",
                            target=f"memory_{mem_id}",
                            type="entity_memory",
                        ))

        # Fetch entity-to-entity edges
        if entity_ids:
            entity_relationships = await self.entity_repo.get_all_entity_relationships(
                user_id=user_id
            )
            for rel in entity_relationships:
                if rel.source_entity_id in entity_id_set and rel.target_entity_id in entity_id_set:
                    # Canonical edge ID for deduplication
                    min_id = min(rel.source_entity_id, rel.target_entity_id)
                    max_id = max(rel.source_entity_id, rel.target_entity_id)
                    edge_id = f"entity_{min_id}_entity_{max_id}"

                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append(SubgraphEdge(
                            id=edge_id,
                            source=f"entity_{rel.source_entity_id}",
                            target=f"entity_{rel.target_entity_id}",
                            type="entity_relationship",
                            data={
                                "relationship_type": rel.relationship_type,
                                "strength": rel.strength,
                                "confidence": rel.confidence,
                                "metadata": rel.metadata,
                            }
                        ))

        return edges
