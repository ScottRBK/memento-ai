"""
REST API endpoints for Graph visualization.

Phase 4 of the Web UI foundation (Issue #3).
Provides graph data (nodes and edges) for visualization UI.
"""
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP
import logging
from typing import List, Dict, Any

from app.middleware.auth import get_user_from_request
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register graph REST routes with FastMCP"""

    # Constants for valid node types
    ALL_NODE_TYPES = {"memory", "entity", "project", "document", "code_artifact"}

    @mcp.custom_route("/api/v1/graph", methods=["GET"])
    async def get_graph(request: Request) -> JSONResponse:
        """
        Get graph data for visualization.

        Returns nodes (memories, entities, projects, documents, code_artifacts) and edges.

        Query params:
            project_id: Filter memories to specific project (optional)
            node_types: Comma-separated list of node types to include
                       (default: memory,entity,project,document,code_artifact)
            include_entities: Legacy param, deprecated in favor of node_types
            limit: Max memories to include (default 100)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        limit_str = params.get("limit", "100")

        # Parse node_types parameter (new approach)
        node_types_str = params.get("node_types")
        if node_types_str:
            # node_types takes precedence over include_entities
            requested_types = {t.strip() for t in node_types_str.split(",") if t.strip()}
            invalid_types = requested_types - ALL_NODE_TYPES
            if invalid_types:
                return JSONResponse(
                    {"error": f"Invalid node_types: {invalid_types}. Valid values: {', '.join(sorted(ALL_NODE_TYPES))}"},
                    status_code=400
                )
            include_memories = "memory" in requested_types
            include_entities = "entity" in requested_types
            include_projects = "project" in requested_types
            include_documents = "document" in requested_types
            include_code_artifacts = "code_artifact" in requested_types
        else:
            # Fallback to legacy include_entities param, default all types
            include_entities_str = params.get("include_entities", "true").lower()
            include_memories = True  # Always include memories by default
            include_entities = include_entities_str == "true"
            include_projects = True  # New default: include all types
            include_documents = True
            include_code_artifacts = True

        # Validate limit parameter
        try:
            limit = min(int(limit_str), 500)
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid limit: {limit_str}. Must be an integer."},
                status_code=400
            )

        # Validate project_id parameter
        project_ids = None
        if project_id_str:
            try:
                project_ids = [int(project_id_str)]
            except ValueError:
                return JSONResponse(
                    {"error": f"Invalid project_id: {project_id_str}. Must be an integer."},
                    status_code=400
                )

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_memory_ids = set()
        seen_edge_ids = set()
        seen_project_ids = set()
        seen_document_ids = set()
        seen_code_artifact_ids = set()
        memories = []  # Store for edge building

        # Get memories
        if include_memories:
            memories, _ = await mcp.memory_service.get_recent_memories(
                user_id=user.id,
                limit=limit,
                project_ids=project_ids
            )

            # Add memory nodes
            for memory in memories:
                seen_memory_ids.add(memory.id)
                nodes.append({
                    "id": f"memory_{memory.id}",
                    "type": "memory",
                    "label": memory.title,
                    "data": {
                        "id": memory.id,
                        "title": memory.title,
                        "importance": memory.importance,
                        "tags": memory.tags,
                        "created_at": memory.created_at.isoformat() if memory.created_at else None
                    }
                })

            # Add edges for memory links
            for memory in memories:
                for linked_id in memory.linked_memory_ids:
                    if linked_id in seen_memory_ids:
                        edge_id = f"memory_{min(memory.id, linked_id)}_memory_{max(memory.id, linked_id)}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory.id}",
                                "target": f"memory_{linked_id}",
                                "type": "memory_link"
                            })

        # Add entity nodes and edges if requested
        seen_entity_ids = set()
        if include_entities:
            # Get all entities (no pagination limit for graph visualization)
            entities, _ = await mcp.entity_service.list_entities(
                user_id=user.id,
                limit=10000  # High limit to get all entities for graph
            )

            for entity in entities:
                seen_entity_ids.add(entity.id)
                nodes.append({
                    "id": f"entity_{entity.id}",
                    "type": "entity",
                    "label": entity.name,
                    "data": {
                        "id": entity.id,
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "created_at": entity.created_at.isoformat() if entity.created_at else None
                    }
                })

            # Add entity-relationship edges (with deduplication for bidirectional display)
            entity_relationships = await mcp.entity_service.get_all_entity_relationships(
                user_id=user.id
            )

            for rel in entity_relationships:
                # Only add edge if both entities are in result set
                if rel.source_entity_id in seen_entity_ids and rel.target_entity_id in seen_entity_ids:
                    # Canonical edge ID for deduplication (bidirectional visualization)
                    min_id = min(rel.source_entity_id, rel.target_entity_id)
                    max_id = max(rel.source_entity_id, rel.target_entity_id)
                    edge_id = f"entity_{min_id}_entity_{max_id}"

                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"entity_{rel.source_entity_id}",
                            "target": f"entity_{rel.target_entity_id}",
                            "type": "entity_relationship",
                            "data": {
                                "relationship_type": rel.relationship_type,
                                "strength": rel.strength,
                                "confidence": rel.confidence,
                                "metadata": rel.metadata
                            }
                        })

            # Add entity-memory edges
            entity_memory_links = await mcp.entity_service.get_all_entity_memory_links(
                user_id=user.id
            )

            for entity_id, mem_id in entity_memory_links:
                # Only add edge if both entity and memory are in result set
                if entity_id in seen_entity_ids and mem_id in seen_memory_ids:
                    # Entity always first for consistent edge ID format
                    edge_id = f"entity_{entity_id}_memory_{mem_id}"

                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"entity_{entity_id}",
                            "target": f"memory_{mem_id}",
                            "type": "entity_memory"
                        })

        # Add project nodes
        projects = []
        if include_projects:
            projects = await mcp.project_service.list_projects(
                user_id=user.id
            )

            for project in projects:
                seen_project_ids.add(project.id)
                nodes.append({
                    "id": f"project_{project.id}",
                    "type": "project",
                    "label": project.name,
                    "data": {
                        "id": project.id,
                        "name": project.name,
                        "project_type": project.project_type.value if hasattr(project.project_type, 'value') else project.project_type,
                        "status": project.status.value if hasattr(project.status, 'value') else project.status,
                        "created_at": project.created_at.isoformat() if project.created_at else None
                    }
                })

        # Add document nodes
        documents = []
        if include_documents:
            documents = await mcp.document_service.list_documents(
                user_id=user.id
            )

            for document in documents:
                seen_document_ids.add(document.id)
                nodes.append({
                    "id": f"document_{document.id}",
                    "type": "document",
                    "label": document.title,
                    "data": {
                        "id": document.id,
                        "title": document.title,
                        "description": document.description,
                        "document_type": document.document_type,
                        "tags": document.tags,
                        "created_at": document.created_at.isoformat() if document.created_at else None
                    }
                })

        # Add code artifact nodes
        code_artifacts = []
        if include_code_artifacts:
            code_artifacts = await mcp.code_artifact_service.list_code_artifacts(
                user_id=user.id
            )

            for artifact in code_artifacts:
                seen_code_artifact_ids.add(artifact.id)
                nodes.append({
                    "id": f"code_artifact_{artifact.id}",
                    "type": "code_artifact",
                    "label": artifact.title,
                    "data": {
                        "id": artifact.id,
                        "title": artifact.title,
                        "description": artifact.description,
                        "language": artifact.language,
                        "tags": artifact.tags,
                        "created_at": artifact.created_at.isoformat() if artifact.created_at else None
                    }
                })

        # Add memory-project edges (from memory.project_ids)
        if include_memories and include_projects:
            for memory in memories:
                for proj_id in (memory.project_ids or []):
                    if proj_id in seen_project_ids:
                        edge_id = f"memory_{memory.id}_project_{proj_id}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory.id}",
                                "target": f"project_{proj_id}",
                                "type": "memory_project"
                            })

        # Add document-project edges (from document.project_id)
        if include_documents and include_projects:
            for document in documents:
                if document.project_id and document.project_id in seen_project_ids:
                    edge_id = f"document_{document.id}_project_{document.project_id}"
                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"document_{document.id}",
                            "target": f"project_{document.project_id}",
                            "type": "document_project"
                        })

        # Add code_artifact-project edges (from artifact.project_id)
        if include_code_artifacts and include_projects:
            for artifact in code_artifacts:
                if artifact.project_id and artifact.project_id in seen_project_ids:
                    edge_id = f"code_artifact_{artifact.id}_project_{artifact.project_id}"
                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"code_artifact_{artifact.id}",
                            "target": f"project_{artifact.project_id}",
                            "type": "code_artifact_project"
                        })

        # Add entity-project edges (from entity_project_association)
        if include_entities and include_projects:
            entity_project_links = await mcp.entity_service.get_all_entity_project_links(
                user_id=user.id
            )
            for entity_id, proj_id in entity_project_links:
                if entity_id in seen_entity_ids and proj_id in seen_project_ids:
                    edge_id = f"entity_{entity_id}_project_{proj_id}"
                    if edge_id not in seen_edge_ids:
                        seen_edge_ids.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"entity_{entity_id}",
                            "target": f"project_{proj_id}",
                            "type": "entity_project"
                        })

        # Add memory-document edges (from memory.document_ids)
        if include_memories and include_documents:
            for memory in memories:
                for doc_id in (memory.document_ids or []):
                    if doc_id in seen_document_ids:
                        edge_id = f"memory_{memory.id}_document_{doc_id}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory.id}",
                                "target": f"document_{doc_id}",
                                "type": "memory_document"
                            })

        # Add memory-code_artifact edges (from memory.code_artifact_ids)
        if include_memories and include_code_artifacts:
            for memory in memories:
                for artifact_id in (memory.code_artifact_ids or []):
                    if artifact_id in seen_code_artifact_ids:
                        edge_id = f"memory_{memory.id}_code_artifact_{artifact_id}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory.id}",
                                "target": f"code_artifact_{artifact_id}",
                                "type": "memory_code_artifact"
                            })

        # Count edges by type for meta
        memory_link_count = len([e for e in edges if e["type"] == "memory_link"])
        entity_relationship_count = len([e for e in edges if e["type"] == "entity_relationship"])
        entity_memory_count = len([e for e in edges if e["type"] == "entity_memory"])
        entity_project_count = len([e for e in edges if e["type"] == "entity_project"])
        memory_project_count = len([e for e in edges if e["type"] == "memory_project"])
        document_project_count = len([e for e in edges if e["type"] == "document_project"])
        code_artifact_project_count = len([e for e in edges if e["type"] == "code_artifact_project"])
        memory_document_count = len([e for e in edges if e["type"] == "memory_document"])
        memory_code_artifact_count = len([e for e in edges if e["type"] == "memory_code_artifact"])

        return JSONResponse({
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "memory_count": len([n for n in nodes if n["type"] == "memory"]),
                "entity_count": len([n for n in nodes if n["type"] == "entity"]),
                "project_count": len([n for n in nodes if n["type"] == "project"]),
                "document_count": len([n for n in nodes if n["type"] == "document"]),
                "code_artifact_count": len([n for n in nodes if n["type"] == "code_artifact"]),
                "edge_count": len(edges),
                "memory_link_count": memory_link_count,
                "entity_relationship_count": entity_relationship_count,
                "entity_memory_count": entity_memory_count,
                "entity_project_count": entity_project_count,
                "memory_project_count": memory_project_count,
                "document_project_count": document_project_count,
                "code_artifact_project_count": code_artifact_project_count,
                "memory_document_count": memory_document_count,
                "memory_code_artifact_count": memory_code_artifact_count
            }
        })

    @mcp.custom_route("/api/v1/graph/memory/{memory_id}", methods=["GET"])
    async def get_memory_subgraph(request: Request) -> JSONResponse:
        """
        Get subgraph centered on a specific memory.

        Returns the memory, its linked memories, and related entities.

        Query params:
            depth: Link traversal depth (1-3, default 1)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        # Validate memory_id path parameter
        try:
            memory_id = int(request.path_params["memory_id"])
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid memory_id: {request.path_params['memory_id']}. Must be an integer."},
                status_code=400
            )

        params = request.query_params
        depth_str = params.get("depth", "1")

        # Validate depth parameter
        try:
            depth = min(int(depth_str), 3)
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid depth: {depth_str}. Must be an integer."},
                status_code=400
            )

        # Get center memory
        try:
            center_memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=memory_id
            )
        except NotFoundError:
            return JSONResponse({"error": "Memory not found"}, status_code=404)

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_memory_ids = set()

        async def add_memory_node(memory, level: int):
            if memory.id in seen_memory_ids:
                return
            seen_memory_ids.add(memory.id)

            nodes.append({
                "id": f"memory_{memory.id}",
                "type": "memory",
                "label": memory.title,
                "level": level,
                "data": {
                    "id": memory.id,
                    "title": memory.title,
                    "importance": memory.importance,
                    "tags": memory.tags,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None
                }
            })

            # Recurse for linked memories if within depth
            if level < depth:
                for linked_id in memory.linked_memory_ids:
                    if linked_id not in seen_memory_ids:
                        linked_memory = await mcp.memory_service.get_memory(
                            user_id=user.id,
                            memory_id=linked_id
                        )
                        if linked_memory:
                            await add_memory_node(linked_memory, level + 1)

                            # Add edge
                            edge_id = f"memory_{min(memory.id, linked_id)}_memory_{max(memory.id, linked_id)}"
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory.id}",
                                "target": f"memory_{linked_id}",
                                "type": "memory_link"
                            })

        # Build subgraph starting from center
        await add_memory_node(center_memory, 0)

        # Add edges between already-seen memories
        seen_edge_ids = set()
        for memory_id_val in seen_memory_ids:
            memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=memory_id_val
            )
            if memory:
                for linked_id in memory.linked_memory_ids:
                    if linked_id in seen_memory_ids:
                        edge_id = f"memory_{min(memory_id_val, linked_id)}_memory_{max(memory_id_val, linked_id)}"
                        if edge_id not in seen_edge_ids:
                            seen_edge_ids.add(edge_id)
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory_id_val}",
                                "target": f"memory_{linked_id}",
                                "type": "memory_link"
                            })

        # Add entities linked to memories in subgraph
        seen_entity_ids = set()
        entity_memory_links = await mcp.entity_service.get_all_entity_memory_links(
            user_id=user.id
        )

        # Identify entities linked to subgraph memories
        relevant_entity_ids = set()
        for entity_id, mem_id in entity_memory_links:
            if mem_id in seen_memory_ids:
                relevant_entity_ids.add(entity_id)

        # Add entity nodes for relevant entities
        for entity_id in relevant_entity_ids:
            entity = await mcp.entity_service.get_entity(
                user_id=user.id,
                entity_id=entity_id
            )
            if entity:
                seen_entity_ids.add(entity.id)
                nodes.append({
                    "id": f"entity_{entity.id}",
                    "type": "entity",
                    "label": entity.name,
                    "data": {
                        "id": entity.id,
                        "name": entity.name,
                        "entity_type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else entity.entity_type,
                        "created_at": entity.created_at.isoformat() if entity.created_at else None
                    }
                })

        # Add entity-memory edges
        for entity_id, mem_id in entity_memory_links:
            if entity_id in seen_entity_ids and mem_id in seen_memory_ids:
                edge_id = f"entity_{entity_id}_memory_{mem_id}"
                if edge_id not in seen_edge_ids:
                    seen_edge_ids.add(edge_id)
                    edges.append({
                        "id": edge_id,
                        "source": f"entity_{entity_id}",
                        "target": f"memory_{mem_id}",
                        "type": "entity_memory"
                    })

        # Add entity-entity relationships for entities in subgraph
        entity_relationships = await mcp.entity_service.get_all_entity_relationships(
            user_id=user.id
        )

        for rel in entity_relationships:
            if rel.source_entity_id in seen_entity_ids and rel.target_entity_id in seen_entity_ids:
                min_id = min(rel.source_entity_id, rel.target_entity_id)
                max_id = max(rel.source_entity_id, rel.target_entity_id)
                edge_id = f"entity_{min_id}_entity_{max_id}"

                if edge_id not in seen_edge_ids:
                    seen_edge_ids.add(edge_id)
                    edges.append({
                        "id": edge_id,
                        "source": f"entity_{rel.source_entity_id}",
                        "target": f"entity_{rel.target_entity_id}",
                        "type": "entity_relationship",
                        "data": {
                            "relationship_type": rel.relationship_type,
                            "strength": rel.strength,
                            "confidence": rel.confidence,
                            "metadata": rel.metadata
                        }
                    })

        # Count by type
        memory_count = len([n for n in nodes if n["type"] == "memory"])
        entity_count = len([n for n in nodes if n["type"] == "entity"])
        memory_link_count = len([e for e in edges if e["type"] == "memory_link"])
        entity_relationship_count = len([e for e in edges if e["type"] == "entity_relationship"])
        entity_memory_count = len([e for e in edges if e["type"] == "entity_memory"])

        return JSONResponse({
            "nodes": nodes,
            "edges": edges,
            "center_memory_id": memory_id,
            "meta": {
                "memory_count": memory_count,
                "entity_count": entity_count,
                "edge_count": len(edges),
                "memory_link_count": memory_link_count,
                "entity_relationship_count": entity_relationship_count,
                "entity_memory_count": entity_memory_count,
                "depth": depth
            }
        })

    @mcp.custom_route("/api/v1/graph/subgraph", methods=["GET"])
    async def get_subgraph(request: Request) -> JSONResponse:
        """
        Get subgraph centered on any node (memory or entity).

        Uses recursive CTE for efficient multi-hop traversal across all edge types.
        This is the recommended endpoint for graph visualization - replaces the
        older /graph/memory/{id} endpoint with better performance and entity support.

        Query params:
            node_id: Center node in format "memory_{id}", "entity_{id}", "project_{id}", "document_{id}", or "code_artifact_{id}" (required)
            depth: Traversal depth 1-3 (default 2)
            node_types: Comma-separated list of types to include (default: "memory,entity,project,document,code_artifact")
            max_nodes: Safety limit (default 200, max 500)

        Returns:
            nodes: List with depth field on each node
            edges: All edges between returned nodes
            meta: Includes center_node_id and truncated flag
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params

        # Validate required node_id parameter
        node_id = params.get("node_id")
        if not node_id:
            return JSONResponse(
                {"error": "Missing required parameter: node_id. Format: 'memory_{id}', 'entity_{id}', 'project_{id}', 'document_{id}', or 'code_artifact_{id}'"},
                status_code=400
            )

        # Validate depth parameter
        depth_str = params.get("depth", "2")
        try:
            depth = int(depth_str)
            if depth < 1:
                return JSONResponse(
                    {"error": f"Invalid depth: {depth}. Must be at least 1."},
                    status_code=400
                )
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid depth: {depth_str}. Must be an integer."},
                status_code=400
            )

        # Parse node_types parameter (default: all 5 types)
        node_types_str = params.get("node_types", "memory,entity,project,document,code_artifact")
        node_types = [t.strip() for t in node_types_str.split(",") if t.strip()]
        valid_types = {"memory", "entity", "project", "document", "code_artifact"}
        invalid_types = set(node_types) - valid_types
        if invalid_types:
            return JSONResponse(
                {"error": f"Invalid node_types: {invalid_types}. Valid values: memory, entity, project, document, code_artifact"},
                status_code=400
            )
        if not node_types:
            node_types = ["memory", "entity", "project", "document", "code_artifact"]

        # Validate max_nodes parameter
        max_nodes_str = params.get("max_nodes", "200")
        try:
            max_nodes = int(max_nodes_str)
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid max_nodes: {max_nodes_str}. Must be an integer."},
                status_code=400
            )

        # Call graph service
        try:
            result = await mcp.graph_service.get_subgraph(
                user_id=user.id,
                center_node_id=node_id,
                depth=depth,
                node_types=node_types,
                max_nodes=max_nodes,
            )
        except ValueError as e:
            # Invalid node_id format
            return JSONResponse({"error": str(e)}, status_code=400)
        except NotFoundError as e:
            return JSONResponse({"error": str(e)}, status_code=404)
        except Exception as e:
            # Log and return detailed error for debugging
            logger.exception(f"Subgraph query failed: {e}")
            return JSONResponse({"error": f"Internal error: {str(e)}"}, status_code=500)

        # Convert Pydantic models to dicts for JSON response
        return JSONResponse({
            "nodes": [node.model_dump() for node in result.nodes],
            "edges": [edge.model_dump() for edge in result.edges],
            "meta": result.meta.model_dump()
        })
