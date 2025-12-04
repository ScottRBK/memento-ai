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

    @mcp.custom_route("/api/v1/graph", methods=["GET"])
    async def get_graph(request: Request) -> JSONResponse:
        """
        Get graph data for visualization.

        Returns nodes (memories, entities) and edges (links between them).

        Query params:
            project_id: Filter to specific project (optional)
            include_entities: Include entity nodes (default true)
            limit: Max memories to include (default 100)
        """
        try:
            user = await get_user_from_request(request, mcp)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=401)

        params = request.query_params
        project_id_str = params.get("project_id")
        include_entities = params.get("include_entities", "true").lower() == "true"
        limit_str = params.get("limit", "100")

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

        # Get memories
        memories, _ = await mcp.memory_service.get_recent_memories(
            user_id=user.id,
            limit=limit,
            project_ids=project_ids
        )

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_memory_ids = set()
        seen_edge_ids = set()

        # First pass: Add all memory nodes and collect IDs
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

        # Second pass: Add edges for all memory links (independent of processing order)
        for memory in memories:
            for linked_id in memory.linked_memory_ids:
                # Only add edge if both memories are in the result set
                if linked_id in seen_memory_ids:
                    # Use canonical edge ID to deduplicate bidirectional links
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
        # Note: EntitySummary from list_entities doesn't include memory_links,
        # so we show all entities. Entity-memory edges would require fetching
        # full entity details which is deferred for performance reasons.
        if include_entities:
            entities = await mcp.entity_service.list_entities(
                user_id=user.id
            )

            for entity in entities:
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

        return JSONResponse({
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "memory_count": len([n for n in nodes if n["type"] == "memory"]),
                "entity_count": len([n for n in nodes if n["type"] == "entity"]),
                "edge_count": len(edges)
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
        for memory_id_val in seen_memory_ids:
            memory = await mcp.memory_service.get_memory(
                user_id=user.id,
                memory_id=memory_id_val
            )
            if memory:
                for linked_id in memory.linked_memory_ids:
                    if linked_id in seen_memory_ids:
                        edge_id = f"memory_{min(memory_id_val, linked_id)}_memory_{max(memory_id_val, linked_id)}"
                        if not any(e["id"] == edge_id for e in edges):
                            edges.append({
                                "id": edge_id,
                                "source": f"memory_{memory_id_val}",
                                "target": f"memory_{linked_id}",
                                "type": "memory_link"
                            })

        return JSONResponse({
            "nodes": nodes,
            "edges": edges,
            "center_memory_id": memory_id,
            "meta": {
                "memory_count": len(nodes),
                "edge_count": len(edges),
                "depth": depth
            }
        })
