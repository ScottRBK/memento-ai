"""
Graph Service - Business logic for graph traversal and visualization

This service implements functionality for efficient graph visualization:
    - Subgraph traversal using recursive CTEs
    - Fetching full node data for memory, entity, project, document, and code_artifact nodes
    - Building edges between nodes in the subgraph
"""
from typing import List, Set, Tuple, Protocol, Any
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
NODE_ID_PATTERN = re.compile(r'^(memory|entity|project|document|code_artifact)_(\d+)$')


# Protocol for project service (to avoid circular imports)
class ProjectServiceProtocol(Protocol):
    async def get_project(self, user_id: UUID, project_id: int) -> Any: ...


# Protocol for document service (to avoid circular imports)
class DocumentServiceProtocol(Protocol):
    async def get_document(self, user_id: UUID, document_id: int) -> Any: ...


# Protocol for code artifact service (to avoid circular imports)
class CodeArtifactServiceProtocol(Protocol):
    async def get_code_artifact(self, user_id: UUID, artifact_id: int) -> Any: ...


class GraphService:
    """Service layer for graph traversal operations.

    Handles business logic for efficient subgraph extraction using
    recursive CTE queries. Coordinates between memory, entity, project,
    document, and code_artifact repositories to build complete subgraph responses.
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        entity_repo: EntityRepository,
        project_service: ProjectServiceProtocol | None = None,
        document_service: DocumentServiceProtocol | None = None,
        code_artifact_service: CodeArtifactServiceProtocol | None = None,
    ):
        """Initialize with repository protocols and optional services.

        Args:
            memory_repo: Memory repository implementing the protocol
            entity_repo: Entity repository implementing the protocol
            project_service: Optional project service for fetching project data
            document_service: Optional document service for fetching document data
            code_artifact_service: Optional code artifact service for fetching artifact data
        """
        self.memory_repo = memory_repo
        self.entity_repo = entity_repo
        self.project_service = project_service
        self.document_service = document_service
        self.code_artifact_service = code_artifact_service
        logger.info("Graph service initialized")

    @staticmethod
    def parse_node_id(node_id: str) -> Tuple[str, int]:
        """Parse node_id string into type and numeric ID.

        Args:
            node_id: Format 'memory_123', 'entity_456', 'project_789',
                     'document_123', or 'code_artifact_456'

        Returns:
            Tuple of (node_type, numeric_id)

        Raises:
            ValueError: If node_id format is invalid
        """
        match = NODE_ID_PATTERN.match(node_id)
        if not match:
            raise ValueError(
                f"Invalid node_id format: '{node_id}'. "
                "Expected 'memory_{{id}}', 'entity_{{id}}', 'project_{{id}}', "
                "'document_{{id}}', or 'code_artifact_{{id}}'."
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
            center_node_id: Format 'memory_123', 'entity_456', 'project_789',
                           'document_123', or 'code_artifact_456'
            depth: Traversal depth 1-3 (default 2, clamped)
            node_types: Filter to any combination of ['memory', 'entity', 'project',
                       'document', 'code_artifact'] (default: all 5 types)
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

        # Determine which node types to include (default: all 5 types)
        if node_types is None:
            node_types = ["memory", "entity", "project", "document", "code_artifact"]
        include_memories = "memory" in node_types
        include_entities = "entity" in node_types
        include_projects = "project" in node_types
        include_documents = "document" in node_types
        include_code_artifacts = "code_artifact" in node_types

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
            include_projects=include_projects,
            include_documents=include_documents,
            include_code_artifacts=include_code_artifacts,
            max_nodes=max_nodes,
        )

        # Separate node IDs by type
        memory_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "memory"]
        entity_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "entity"]
        project_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "project"]
        document_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "document"]
        code_artifact_ids = [n["node_id"] for n in raw_nodes if n["node_type"] == "code_artifact"]

        # Build depth lookup
        depth_lookup = {
            (n["node_type"], n["node_id"]): n["depth"]
            for n in raw_nodes
        }

        # Fetch full node data
        nodes = await self._fetch_node_data(
            user_id, memory_ids, entity_ids, project_ids, document_ids, code_artifact_ids, depth_lookup
        )

        # Fetch edges between nodes in the subgraph
        edges = await self._fetch_edges(
            user_id, memory_ids, entity_ids, project_ids, document_ids, code_artifact_ids
        )

        # Build metadata
        memory_count = len([n for n in nodes if n.type == "memory"])
        entity_count = len([n for n in nodes if n.type == "entity"])
        project_count = len([n for n in nodes if n.type == "project"])
        document_count = len([n for n in nodes if n.type == "document"])
        code_artifact_count = len([n for n in nodes if n.type == "code_artifact"])
        memory_link_count = len([e for e in edges if e.type == "memory_link"])
        entity_relationship_count = len([e for e in edges if e.type == "entity_relationship"])
        entity_memory_count = len([e for e in edges if e.type == "entity_memory"])
        entity_project_count = len([e for e in edges if e.type == "entity_project"])
        memory_project_count = len([e for e in edges if e.type == "memory_project"])
        document_project_count = len([e for e in edges if e.type == "document_project"])
        code_artifact_project_count = len([e for e in edges if e.type == "code_artifact_project"])
        memory_document_count = len([e for e in edges if e.type == "memory_document"])
        memory_code_artifact_count = len([e for e in edges if e.type == "memory_code_artifact"])

        meta = SubgraphMeta(
            center_node_id=center_node_id,
            depth=depth,
            node_types=node_types,
            max_nodes=max_nodes,
            memory_count=memory_count,
            entity_count=entity_count,
            project_count=project_count,
            document_count=document_count,
            code_artifact_count=code_artifact_count,
            edge_count=len(edges),
            memory_link_count=memory_link_count,
            entity_relationship_count=entity_relationship_count,
            entity_memory_count=entity_memory_count,
            entity_project_count=entity_project_count,
            memory_project_count=memory_project_count,
            document_project_count=document_project_count,
            code_artifact_project_count=code_artifact_project_count,
            memory_document_count=memory_document_count,
            memory_code_artifact_count=memory_code_artifact_count,
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
        elif center_type == "entity":
            entity = await self.entity_repo.get_entity_by_id(
                user_id=user_id,
                entity_id=center_id
            )
            if entity is None:
                raise NotFoundError(f"Entity {center_id} not found")
        elif center_type == "project":
            if self.project_service is None:
                raise NotFoundError("Project service not available")
            project = await self.project_service.get_project(
                user_id=user_id,
                project_id=center_id
            )
            if project is None:
                raise NotFoundError(f"Project {center_id} not found")
        elif center_type == "document":
            if self.document_service is None:
                raise NotFoundError("Document service not available")
            document = await self.document_service.get_document(
                user_id=user_id,
                document_id=center_id
            )
            if document is None:
                raise NotFoundError(f"Document {center_id} not found")
        elif center_type == "code_artifact":
            if self.code_artifact_service is None:
                raise NotFoundError("Code artifact service not available")
            artifact = await self.code_artifact_service.get_code_artifact(
                user_id=user_id,
                artifact_id=center_id
            )
            if artifact is None:
                raise NotFoundError(f"Code artifact {center_id} not found")
        else:
            raise ValueError(f"Unknown center_type: {center_type}")

    async def _fetch_node_data(
        self,
        user_id: UUID,
        memory_ids: List[int],
        entity_ids: List[int],
        project_ids: List[int],
        document_ids: List[int],
        code_artifact_ids: List[int],
        depth_lookup: dict
    ) -> List[SubgraphNode]:
        """Fetch full data for all node types.

        Args:
            user_id: User ID for ownership
            memory_ids: List of memory IDs to fetch
            entity_ids: List of entity IDs to fetch
            project_ids: List of project IDs to fetch
            document_ids: List of document IDs to fetch
            code_artifact_ids: List of code artifact IDs to fetch
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

        # Fetch projects
        if self.project_service and project_ids:
            for project_id in project_ids:
                try:
                    project = await self.project_service.get_project(
                        user_id=user_id,
                        project_id=project_id
                    )
                    if project is None:
                        logger.warning(f"Project {project_id} not found during fetch")
                        continue
                    nodes.append(SubgraphNode(
                        id=f"project_{project.id}",
                        type="project",
                        depth=depth_lookup.get(("project", project_id), 0),
                        label=project.name,
                        data={
                            "id": project.id,
                            "name": project.name,
                            "description": project.description,
                            "project_type": project.project_type.value if hasattr(project.project_type, 'value') else project.project_type,
                            "status": project.status.value if hasattr(project.status, 'value') else project.status,
                            "created_at": project.created_at.isoformat() if project.created_at else None,
                        }
                    ))
                except NotFoundError:
                    logger.warning(f"Project {project_id} not found during fetch")
                    continue

        # Fetch documents
        if self.document_service and document_ids:
            for document_id in document_ids:
                try:
                    document = await self.document_service.get_document(
                        user_id=user_id,
                        document_id=document_id
                    )
                    if document is None:
                        logger.warning(f"Document {document_id} not found during fetch")
                        continue
                    nodes.append(SubgraphNode(
                        id=f"document_{document.id}",
                        type="document",
                        depth=depth_lookup.get(("document", document_id), 0),
                        label=document.title,
                        data={
                            "id": document.id,
                            "title": document.title,
                            "description": document.description,
                            "document_type": document.document_type.value if hasattr(document.document_type, 'value') else document.document_type,
                            "project_id": document.project_id,
                            "created_at": document.created_at.isoformat() if document.created_at else None,
                        }
                    ))
                except NotFoundError:
                    logger.warning(f"Document {document_id} not found during fetch")
                    continue

        # Fetch code artifacts
        if self.code_artifact_service and code_artifact_ids:
            for artifact_id in code_artifact_ids:
                try:
                    artifact = await self.code_artifact_service.get_code_artifact(
                        user_id=user_id,
                        artifact_id=artifact_id
                    )
                    if artifact is None:
                        logger.warning(f"Code artifact {artifact_id} not found during fetch")
                        continue
                    nodes.append(SubgraphNode(
                        id=f"code_artifact_{artifact.id}",
                        type="code_artifact",
                        depth=depth_lookup.get(("code_artifact", artifact_id), 0),
                        label=artifact.title,
                        data={
                            "id": artifact.id,
                            "title": artifact.title,
                            "description": artifact.description,
                            "language": artifact.language,
                            "project_id": artifact.project_id,
                            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                        }
                    ))
                except NotFoundError:
                    logger.warning(f"Code artifact {artifact_id} not found during fetch")
                    continue

        return nodes

    async def _fetch_edges(
        self,
        user_id: UUID,
        memory_ids: List[int],
        entity_ids: List[int],
        project_ids: List[int],
        document_ids: List[int],
        code_artifact_ids: List[int]
    ) -> List[SubgraphEdge]:
        """Fetch all edges between nodes in the subgraph.

        Retrieves:
        - Memory-to-memory links
        - Entity-to-memory links
        - Entity-to-entity relationships
        - Memory-to-project links
        - Document-to-project links
        - CodeArtifact-to-project links
        - Memory-to-document links
        - Memory-to-code_artifact links

        Args:
            user_id: User ID for ownership
            memory_ids: List of memory IDs in subgraph
            entity_ids: List of entity IDs in subgraph
            project_ids: List of project IDs in subgraph
            document_ids: List of document IDs in subgraph
            code_artifact_ids: List of code artifact IDs in subgraph

        Returns:
            List of SubgraphEdge
        """
        edges: List[SubgraphEdge] = []
        seen_edge_ids: Set[str] = set()

        memory_id_set = set(memory_ids)
        entity_id_set = set(entity_ids)
        project_id_set = set(project_ids)
        document_id_set = set(document_ids)
        code_artifact_id_set = set(code_artifact_ids)

        # Fetch memory-to-memory edges
        if memory_ids:
            for memory_id in memory_ids:
                try:
                    memory = await self.memory_repo.get_memory_by_id(
                        user_id=user_id,
                        memory_id=memory_id
                    )
                    # Memory -> Memory links
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

                    # Memory -> Project links
                    for proj_id in memory.project_ids:
                        if proj_id in project_id_set:
                            edge_id = f"memory_{memory_id}_project_{proj_id}"
                            if edge_id not in seen_edge_ids:
                                seen_edge_ids.add(edge_id)
                                edges.append(SubgraphEdge(
                                    id=edge_id,
                                    source=f"memory_{memory_id}",
                                    target=f"project_{proj_id}",
                                    type="memory_project",
                                ))

                    # Memory -> Document links
                    for doc_id in memory.document_ids:
                        if doc_id in document_id_set:
                            edge_id = f"memory_{memory_id}_document_{doc_id}"
                            if edge_id not in seen_edge_ids:
                                seen_edge_ids.add(edge_id)
                                edges.append(SubgraphEdge(
                                    id=edge_id,
                                    source=f"memory_{memory_id}",
                                    target=f"document_{doc_id}",
                                    type="memory_document",
                                ))

                    # Memory -> Code Artifact links
                    for artifact_id in memory.code_artifact_ids:
                        if artifact_id in code_artifact_id_set:
                            edge_id = f"memory_{memory_id}_code_artifact_{artifact_id}"
                            if edge_id not in seen_edge_ids:
                                seen_edge_ids.add(edge_id)
                                edges.append(SubgraphEdge(
                                    id=edge_id,
                                    source=f"memory_{memory_id}",
                                    target=f"code_artifact_{artifact_id}",
                                    type="memory_code_artifact",
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

        # Fetch entity-to-project edges
        if entity_ids and project_ids:
            entity_project_links = await self.entity_repo.get_all_entity_project_links(
                user_id=user_id
            )
            for entity_id, proj_id in entity_project_links:
                if entity_id in entity_id_set and proj_id in project_id_set:
                    edge_id = f"entity_{entity_id}_project_{proj_id}"
                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append(SubgraphEdge(
                            id=edge_id,
                            source=f"entity_{entity_id}",
                            target=f"project_{proj_id}",
                            type="entity_project",
                        ))

        # Fetch document-to-project edges
        if self.document_service and document_ids and project_ids:
            for document_id in document_ids:
                try:
                    document = await self.document_service.get_document(
                        user_id=user_id,
                        document_id=document_id
                    )
                    if document and document.project_id and document.project_id in project_id_set:
                        edge_id = f"document_{document_id}_project_{document.project_id}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append(SubgraphEdge(
                                id=edge_id,
                                source=f"document_{document_id}",
                                target=f"project_{document.project_id}",
                                type="document_project",
                            ))
                except NotFoundError:
                    continue

        # Fetch code_artifact-to-project edges
        if self.code_artifact_service and code_artifact_ids and project_ids:
            for artifact_id in code_artifact_ids:
                try:
                    artifact = await self.code_artifact_service.get_code_artifact(
                        user_id=user_id,
                        artifact_id=artifact_id
                    )
                    if artifact and artifact.project_id and artifact.project_id in project_id_set:
                        edge_id = f"code_artifact_{artifact_id}_project_{artifact.project_id}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append(SubgraphEdge(
                                id=edge_id,
                                source=f"code_artifact_{artifact_id}",
                                target=f"project_{artifact.project_id}",
                                type="code_artifact_project",
                            ))
                except NotFoundError:
                    continue

        return edges
