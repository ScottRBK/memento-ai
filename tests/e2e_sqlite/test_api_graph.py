"""
E2E tests for Graph REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/graph endpoints.
"""
import pytest


class TestGraphAPI:
    """Test GET /api/v1/graph endpoint."""

    @pytest.mark.asyncio
    async def test_get_graph_empty(self, http_client):
        """GET /api/v1/graph returns empty graph initially."""
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert "meta" in data
        assert data["meta"]["memory_count"] == 0
        assert data["meta"]["entity_count"] == 0
        assert data["meta"]["edge_count"] == 0

    @pytest.mark.asyncio
    async def test_get_graph_with_memories(self, http_client):
        """GET /api/v1/graph returns memory nodes."""
        # Create some memories
        await http_client.post("/api/v1/memories", json={
            "title": "Graph Memory 1",
            "content": "First memory for graph test",
            "context": "Testing graph API",
            "keywords": ["graph", "test"],
            "tags": ["test"],
            "importance": 7
        })
        await http_client.post("/api/v1/memories", json={
            "title": "Graph Memory 2",
            "content": "Second memory for graph test",
            "context": "Testing graph API",
            "keywords": ["graph", "test"],
            "tags": ["test"],
            "importance": 7
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) >= 2
        assert data["meta"]["memory_count"] >= 2

        # Check node structure
        memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
        assert len(memory_nodes) >= 2
        for node in memory_nodes:
            assert "id" in node
            assert "label" in node
            assert "data" in node
            assert node["id"].startswith("memory_")

    @pytest.mark.asyncio
    async def test_get_graph_with_entities(self, http_client):
        """GET /api/v1/graph returns entity nodes when include_entities=true."""
        # Create an entity
        await http_client.post("/api/v1/entities", json={
            "name": "Graph Test Entity",
            "entity_type": "Organization",
            "notes": "Entity for graph test"
        })

        # Get graph with entities
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        entity_nodes = [n for n in data["nodes"] if n["type"] == "entity"]
        assert len(entity_nodes) >= 1
        for node in entity_nodes:
            assert node["id"].startswith("entity_")
            assert "name" in node["data"]

    @pytest.mark.asyncio
    async def test_get_graph_without_entities(self, http_client):
        """GET /api/v1/graph excludes entities when include_entities=false."""
        # Create entity
        await http_client.post("/api/v1/entities", json={
            "name": "Excluded Entity",
            "entity_type": "Individual",
            "notes": "Should be excluded"
        })

        # Create memory
        await http_client.post("/api/v1/memories", json={
            "title": "Graph Memory Only",
            "content": "Memory without entities in graph",
            "context": "Testing exclude entities",
            "keywords": ["graph"],
            "tags": ["test"],
            "importance": 7
        })

        # Get graph without entities
        response = await http_client.get("/api/v1/graph?include_entities=false")
        assert response.status_code == 200
        data = response.json()

        entity_nodes = [n for n in data["nodes"] if n["type"] == "entity"]
        assert len(entity_nodes) == 0

    @pytest.mark.asyncio
    async def test_get_graph_with_memory_links(self, http_client):
        """GET /api/v1/graph returns edges for linked memories."""
        # Create two memories
        mem1_response = await http_client.post("/api/v1/memories", json={
            "title": "Linked Memory A",
            "content": "First linked memory for graph edge test",
            "context": "Testing graph edges",
            "keywords": ["linkA"],
            "tags": ["edge-test"],
            "importance": 7
        })
        mem1_id = mem1_response.json()["id"]

        mem2_response = await http_client.post("/api/v1/memories", json={
            "title": "Linked Memory B",
            "content": "Second linked memory for graph edge test",
            "context": "Testing graph edges",
            "keywords": ["linkB"],
            "tags": ["edge-test"],
            "importance": 7
        })
        mem2_id = mem2_response.json()["id"]

        # Link them
        await http_client.post(f"/api/v1/memories/{mem1_id}/links", json={
            "related_ids": [mem2_id]
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check for edge between the memories
        memory_link_edges = [e for e in data["edges"] if e["type"] == "memory_link"]
        # Should have at least one edge
        assert len(memory_link_edges) >= 1

    @pytest.mark.asyncio
    async def test_get_graph_with_limit(self, http_client):
        """GET /api/v1/graph respects limit parameter."""
        # Create multiple memories
        for i in range(5):
            await http_client.post("/api/v1/memories", json={
                "title": f"Limit Test Memory {i}",
                "content": f"Memory {i} for limit test",
                "context": "Testing limit",
                "keywords": [f"limit{i}"],
                "tags": ["limit-test"],
                "importance": 7
            })

        # Get graph with limit
        response = await http_client.get("/api/v1/graph?limit=2")
        assert response.status_code == 200
        data = response.json()

        memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
        assert len(memory_nodes) <= 2


class TestMemorySubgraph:
    """Test GET /api/v1/graph/memory/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_memory_subgraph(self, http_client):
        """GET /api/v1/graph/memory/{id} returns subgraph centered on memory."""
        # Create a memory
        mem_response = await http_client.post("/api/v1/memories", json={
            "title": "Center Memory",
            "content": "Memory at the center of subgraph",
            "context": "Testing subgraph",
            "keywords": ["center"],
            "tags": ["subgraph-test"],
            "importance": 7
        })
        memory_id = mem_response.json()["id"]

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/memory/{memory_id}")
        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert data["center_memory_id"] == memory_id
        assert "meta" in data

        # Should include the center memory
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"memory_{memory_id}" in node_ids

    @pytest.mark.asyncio
    async def test_get_memory_subgraph_not_found(self, http_client):
        """GET /api/v1/graph/memory/{id} returns 404 for missing memory."""
        response = await http_client.get("/api/v1/graph/memory/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_memory_subgraph_with_links(self, http_client):
        """GET /api/v1/graph/memory/{id} includes linked memories."""
        # Create center memory
        center_response = await http_client.post("/api/v1/memories", json={
            "title": "Subgraph Center",
            "content": "Center of the subgraph",
            "context": "Testing subgraph links",
            "keywords": ["subgraphCenter"],
            "tags": ["subgraph"],
            "importance": 7
        })
        center_id = center_response.json()["id"]

        # Create linked memory
        linked_response = await http_client.post("/api/v1/memories", json={
            "title": "Linked to Center",
            "content": "Memory linked to center",
            "context": "Testing subgraph links",
            "keywords": ["subgraphLinked"],
            "tags": ["subgraph"],
            "importance": 7
        })
        linked_id = linked_response.json()["id"]

        # Link them
        await http_client.post(f"/api/v1/memories/{center_id}/links", json={
            "related_ids": [linked_id]
        })

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/memory/{center_id}")
        assert response.status_code == 200
        data = response.json()

        # Should include both memories
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"memory_{center_id}" in node_ids
        assert f"memory_{linked_id}" in node_ids

        # Should have edge between them
        assert len(data["edges"]) >= 1

    @pytest.mark.asyncio
    async def test_get_memory_subgraph_with_depth(self, http_client):
        """GET /api/v1/graph/memory/{id} respects depth parameter."""
        # Create chain of linked memories
        mem1_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Chain 1",
            "content": "First in chain",
            "context": "Testing depth",
            "keywords": ["depthChain1"],
            "tags": ["depth"],
            "importance": 7
        })
        mem1_id = mem1_response.json()["id"]

        mem2_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Chain 2",
            "content": "Second in chain",
            "context": "Testing depth",
            "keywords": ["depthChain2"],
            "tags": ["depth"],
            "importance": 7
        })
        mem2_id = mem2_response.json()["id"]

        mem3_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Chain 3",
            "content": "Third in chain",
            "context": "Testing depth",
            "keywords": ["depthChain3"],
            "tags": ["depth"],
            "importance": 7
        })
        mem3_id = mem3_response.json()["id"]

        # Link: 1 -> 2 -> 3
        await http_client.post(f"/api/v1/memories/{mem1_id}/links", json={
            "related_ids": [mem2_id]
        })
        await http_client.post(f"/api/v1/memories/{mem2_id}/links", json={
            "related_ids": [mem3_id]
        })

        # Get subgraph with depth=1 (should only get mem1 and mem2)
        response = await http_client.get(f"/api/v1/graph/memory/{mem1_id}?depth=1")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["depth"] == 1

        # Get subgraph with depth=2 (should get all three)
        response = await http_client.get(f"/api/v1/graph/memory/{mem1_id}?depth=2")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["depth"] == 2
        # With depth=2, we should reach mem3 through mem2
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"memory_{mem1_id}" in node_ids
        assert f"memory_{mem2_id}" in node_ids
