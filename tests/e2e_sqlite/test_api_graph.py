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

    @pytest.mark.asyncio
    async def test_get_graph_invalid_limit(self, http_client):
        """GET /api/v1/graph returns 400 for invalid limit."""
        response = await http_client.get("/api/v1/graph?limit=not_a_number")
        assert response.status_code == 400
        assert "Invalid limit" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_get_graph_invalid_project_id(self, http_client):
        """GET /api/v1/graph returns 400 for invalid project_id."""
        response = await http_client.get("/api/v1/graph?project_id=not_a_number")
        assert response.status_code == 400
        assert "Invalid project_id" in response.json()["error"]


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

    @pytest.mark.asyncio
    async def test_get_memory_subgraph_invalid_memory_id(self, http_client):
        """GET /api/v1/graph/memory/{id} returns 400 for invalid memory_id."""
        response = await http_client.get("/api/v1/graph/memory/not_a_number")
        assert response.status_code == 400
        assert "Invalid memory_id" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_get_memory_subgraph_invalid_depth(self, http_client):
        """GET /api/v1/graph/memory/{id} returns 400 for invalid depth."""
        # First create a memory
        mem_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Validation Test",
            "content": "Memory for testing depth validation",
            "context": "Testing depth",
            "keywords": ["depthTest"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = mem_response.json()["id"]

        response = await http_client.get(f"/api/v1/graph/memory/{memory_id}?depth=not_a_number")
        assert response.status_code == 400
        assert "Invalid depth" in response.json()["error"]


class TestGraphEntityEdges:
    """Test entity-entity and entity-memory edges in graph API."""

    @pytest.mark.asyncio
    async def test_graph_includes_entity_relationship_edges(self, http_client):
        """GET /api/v1/graph includes entity-relationship edges."""
        # Create two entities
        entity1_resp = await http_client.post("/api/v1/entities", json={
            "name": "Alice Developer",
            "entity_type": "Individual"
        })
        entity1_id = entity1_resp.json()["id"]

        entity2_resp = await http_client.post("/api/v1/entities", json={
            "name": "TechCorp Inc",
            "entity_type": "Organization"
        })
        entity2_id = entity2_resp.json()["id"]

        # Create relationship: Alice works_at TechCorp
        await http_client.post(f"/api/v1/entities/{entity1_id}/relationships", json={
            "target_entity_id": entity2_id,
            "relationship_type": "works_at",
            "strength": 0.9,
            "confidence": 0.95
        })

        # Get graph
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        # Find entity_relationship edges
        entity_rel_edges = [e for e in data["edges"] if e["type"] == "entity_relationship"]
        assert len(entity_rel_edges) >= 1

        # Verify edge structure
        edge = entity_rel_edges[0]
        assert "data" in edge
        assert edge["data"]["relationship_type"] == "works_at"
        assert edge["data"]["strength"] == 0.9
        assert edge["data"]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_graph_includes_entity_memory_edges(self, http_client):
        """GET /api/v1/graph includes entity-memory edges."""
        # Create memory
        mem_resp = await http_client.post("/api/v1/memories", json={
            "title": "Project kickoff meeting",
            "content": "Discussed project timeline",
            "context": "Meeting notes",
            "keywords": ["meeting"],
            "tags": ["project"],
            "importance": 7
        })
        memory_id = mem_resp.json()["id"]

        # Create entity
        entity_resp = await http_client.post("/api/v1/entities", json={
            "name": "Project Alpha",
            "entity_type": "Team"
        })
        entity_id = entity_resp.json()["id"]

        # Link entity to memory
        await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
            "memory_id": memory_id
        })

        # Get graph
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        # Find entity_memory edges
        entity_mem_edges = [e for e in data["edges"] if e["type"] == "entity_memory"]
        assert len(entity_mem_edges) >= 1

        # Verify edge structure
        edge = entity_mem_edges[0]
        assert edge["source"] == f"entity_{entity_id}"
        assert edge["target"] == f"memory_{memory_id}"
        assert edge["id"] == f"entity_{entity_id}_memory_{memory_id}"

    @pytest.mark.asyncio
    async def test_entity_relationship_deduplication_bidirectional(self, http_client):
        """Entity relationships are deduplicated for bidirectional display."""
        # Create two entities
        entity_a_resp = await http_client.post("/api/v1/entities", json={
            "name": "Entity A",
            "entity_type": "Organization"
        })
        entity_a_id = entity_a_resp.json()["id"]

        entity_b_resp = await http_client.post("/api/v1/entities", json={
            "name": "Entity B",
            "entity_type": "Organization"
        })
        entity_b_id = entity_b_resp.json()["id"]

        # Create A -> B relationship
        await http_client.post(f"/api/v1/entities/{entity_a_id}/relationships", json={
            "target_entity_id": entity_b_id,
            "relationship_type": "partners_with"
        })

        # Create B -> A relationship (reverse direction)
        await http_client.post(f"/api/v1/entities/{entity_b_id}/relationships", json={
            "target_entity_id": entity_a_id,
            "relationship_type": "partners_with"
        })

        # Get graph
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        # Count entity_relationship edges between A and B
        min_id = min(entity_a_id, entity_b_id)
        max_id = max(entity_a_id, entity_b_id)
        expected_edge_id = f"entity_{min_id}_entity_{max_id}"

        matching_edges = [
            e for e in data["edges"]
            if e["type"] == "entity_relationship" and e["id"] == expected_edge_id
        ]

        # Should only have ONE edge despite two relationships
        assert len(matching_edges) == 1

    @pytest.mark.asyncio
    async def test_entity_edges_excluded_when_include_entities_false(self, http_client):
        """Entity edges are excluded when include_entities=false."""
        # Create entity and memory with relationship
        entity_resp = await http_client.post("/api/v1/entities", json={
            "name": "Test Entity",
            "entity_type": "Organization"
        })
        entity_id = entity_resp.json()["id"]

        mem_resp = await http_client.post("/api/v1/memories", json={
            "title": "Test Memory",
            "content": "Test content",
            "context": "Testing",
            "keywords": ["test"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = mem_resp.json()["id"]

        await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
            "memory_id": memory_id
        })

        # Get graph WITHOUT entities
        response = await http_client.get("/api/v1/graph?include_entities=false")
        assert response.status_code == 200
        data = response.json()

        # Should have no entity edges
        entity_rel_edges = [e for e in data["edges"] if e["type"] == "entity_relationship"]
        entity_mem_edges = [e for e in data["edges"] if e["type"] == "entity_memory"]

        assert len(entity_rel_edges) == 0
        assert len(entity_mem_edges) == 0

    @pytest.mark.asyncio
    async def test_graph_meta_includes_edge_counts_by_type(self, http_client):
        """Graph meta includes separate counts for each edge type."""
        # Create test data with all edge types
        # Memory link
        mem1_resp = await http_client.post("/api/v1/memories", json={
            "title": "Memory 1", "content": "Content 1", "context": "Context",
            "keywords": ["k1"], "tags": ["t1"], "importance": 7
        })
        mem1_id = mem1_resp.json()["id"]

        mem2_resp = await http_client.post("/api/v1/memories", json={
            "title": "Memory 2", "content": "Content 2", "context": "Context",
            "keywords": ["k2"], "tags": ["t2"], "importance": 7
        })
        mem2_id = mem2_resp.json()["id"]

        await http_client.post(f"/api/v1/memories/{mem1_id}/links", json={
            "related_ids": [mem2_id]
        })

        # Entity relationship
        ent1_resp = await http_client.post("/api/v1/entities", json={
            "name": "Entity 1", "entity_type": "Organization"
        })
        ent1_id = ent1_resp.json()["id"]

        ent2_resp = await http_client.post("/api/v1/entities", json={
            "name": "Entity 2", "entity_type": "Organization"
        })
        ent2_id = ent2_resp.json()["id"]

        await http_client.post(f"/api/v1/entities/{ent1_id}/relationships", json={
            "target_entity_id": ent2_id,
            "relationship_type": "related_to"
        })

        # Entity-memory link
        await http_client.post(f"/api/v1/entities/{ent1_id}/memories", json={
            "memory_id": mem1_id
        })

        # Get graph
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        # Verify meta includes typed counts
        meta = data["meta"]
        assert "memory_link_count" in meta
        assert "entity_relationship_count" in meta
        assert "entity_memory_count" in meta
        assert meta["memory_link_count"] >= 1
        assert meta["entity_relationship_count"] >= 1
        assert meta["entity_memory_count"] >= 1

    @pytest.mark.asyncio
    async def test_entity_edges_only_appear_when_both_nodes_in_result(self, http_client):
        """Entity edges only appear when both endpoint nodes are in the result set."""
        # Create two entities
        ent1_resp = await http_client.post("/api/v1/entities", json={
            "name": "Visible Entity", "entity_type": "Organization"
        })
        ent1_id = ent1_resp.json()["id"]

        ent2_resp = await http_client.post("/api/v1/entities", json={
            "name": "Also Visible Entity", "entity_type": "Organization"
        })
        ent2_id = ent2_resp.json()["id"]

        # Create relationship
        await http_client.post(f"/api/v1/entities/{ent1_id}/relationships", json={
            "target_entity_id": ent2_id,
            "relationship_type": "connected_to"
        })

        # Get graph with entities - edge should appear
        response = await http_client.get("/api/v1/graph?include_entities=true")
        assert response.status_code == 200
        data = response.json()

        entity_rel_edges = [e for e in data["edges"] if e["type"] == "entity_relationship"]
        assert len(entity_rel_edges) >= 1

    @pytest.mark.asyncio
    async def test_subgraph_includes_entity_edges_for_related_entities(self, http_client):
        """Memory subgraph includes entities linked to memories and their edges."""
        # Create memory
        mem_resp = await http_client.post("/api/v1/memories", json={
            "title": "Center Memory for Entity Test",
            "content": "Central memory content",
            "context": "Subgraph entity test",
            "keywords": ["subgraph", "entity"],
            "tags": ["test"],
            "importance": 8
        })
        memory_id = mem_resp.json()["id"]

        # Create two entities
        ent1_resp = await http_client.post("/api/v1/entities", json={
            "name": "Linked Entity 1", "entity_type": "Individual"
        })
        ent1_id = ent1_resp.json()["id"]

        ent2_resp = await http_client.post("/api/v1/entities", json={
            "name": "Linked Entity 2", "entity_type": "Individual"
        })
        ent2_id = ent2_resp.json()["id"]

        # Link both entities to memory
        await http_client.post(f"/api/v1/entities/{ent1_id}/memories", json={
            "memory_id": memory_id
        })
        await http_client.post(f"/api/v1/entities/{ent2_id}/memories", json={
            "memory_id": memory_id
        })

        # Create relationship between entities
        await http_client.post(f"/api/v1/entities/{ent1_id}/relationships", json={
            "target_entity_id": ent2_id,
            "relationship_type": "collaborates_with",
            "strength": 0.8
        })

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/memory/{memory_id}")
        assert response.status_code == 200
        data = response.json()

        # Should include entity nodes
        entity_nodes = [n for n in data["nodes"] if n["type"] == "entity"]
        assert len(entity_nodes) == 2

        # Should include entity-memory edges
        entity_mem_edges = [e for e in data["edges"] if e["type"] == "entity_memory"]
        assert len(entity_mem_edges) == 2

        # Should include entity-entity edge
        entity_rel_edges = [e for e in data["edges"] if e["type"] == "entity_relationship"]
        assert len(entity_rel_edges) == 1
        assert entity_rel_edges[0]["data"]["relationship_type"] == "collaborates_with"


class TestSubgraphEndpoint:
    """Test GET /api/v1/graph/subgraph endpoint with recursive CTE traversal."""

    @pytest.mark.asyncio
    async def test_subgraph_from_memory_center(self, http_client):
        """Subgraph traversal starting from a memory node."""
        # Create a memory
        mem_response = await http_client.post("/api/v1/memories", json={
            "title": "CTE Center Memory",
            "content": "Memory at the center of CTE subgraph",
            "context": "Testing CTE subgraph",
            "keywords": ["cte_center"],
            "tags": ["cte-test"],
            "importance": 7
        })
        memory_id = mem_response.json()["id"]

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{memory_id}")
        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert "meta" in data
        assert data["meta"]["center_node_id"] == f"memory_{memory_id}"

        # Should include the center memory with depth 0
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"memory_{memory_id}" in node_ids

        center_node = next(n for n in data["nodes"] if n["id"] == f"memory_{memory_id}")
        assert center_node["depth"] == 0

    @pytest.mark.asyncio
    async def test_subgraph_from_entity_center(self, http_client):
        """Subgraph traversal starting from an entity node."""
        # Create an entity
        entity_response = await http_client.post("/api/v1/entities", json={
            "name": "CTE Center Entity",
            "entity_type": "Organization",
            "notes": "Entity at center of CTE subgraph"
        })
        entity_id = entity_response.json()["id"]

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=entity_{entity_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["meta"]["center_node_id"] == f"entity_{entity_id}"

        # Should include the center entity with depth 0
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"entity_{entity_id}" in node_ids

        center_node = next(n for n in data["nodes"] if n["id"] == f"entity_{entity_id}")
        assert center_node["depth"] == 0

    @pytest.mark.asyncio
    async def test_subgraph_depth_limits(self, http_client):
        """Depth parameter controls traversal depth."""
        # Disable auto-linking for this test to control exact graph structure
        from app.config.settings import settings
        original_auto_link = settings.MEMORY_NUM_AUTO_LINK
        settings.MEMORY_NUM_AUTO_LINK = 0

        try:
            # Create chain of linked memories: M1 -> M2 -> M3
            mem1_response = await http_client.post("/api/v1/memories", json={
                "title": "Antarctic Penguin Migration",
                "content": "Emperor penguins travel 70km across ice to breeding grounds",
                "context": "Wildlife documentary research",
                "keywords": ["penguin", "antarctica", "migration"],
                "tags": ["depth-test"],
                "importance": 7
            })
            mem1_id = mem1_response.json()["id"]

            mem2_response = await http_client.post("/api/v1/memories", json={
                "title": "Quantum Entanglement Properties",
                "content": "Particles maintain correlated states regardless of distance",
                "context": "Physics lecture notes",
                "keywords": ["quantum", "physics", "entanglement"],
                "tags": ["depth-test"],
                "importance": 7
            })
            mem2_id = mem2_response.json()["id"]

            mem3_response = await http_client.post("/api/v1/memories", json={
                "title": "Renaissance Art Techniques",
                "content": "Sfumato technique developed by Leonardo da Vinci for soft edges",
                "context": "Art history seminar",
                "keywords": ["art", "renaissance", "painting"],
                "tags": ["depth-test"],
                "importance": 7
            })
            mem3_id = mem3_response.json()["id"]

            # Link: M1 -> M2 -> M3
            await http_client.post(f"/api/v1/memories/{mem1_id}/links", json={
                "related_ids": [mem2_id]
            })
            await http_client.post(f"/api/v1/memories/{mem2_id}/links", json={
                "related_ids": [mem3_id]
            })

            # Depth 1: Should get M1 and M2 only
            response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{mem1_id}&depth=1")
            assert response.status_code == 200
            data = response.json()
            assert data["meta"]["depth"] == 1

            node_ids = {n["id"] for n in data["nodes"]}
            assert f"memory_{mem1_id}" in node_ids
            assert f"memory_{mem2_id}" in node_ids
            # M3 should NOT be present at depth 1
            assert f"memory_{mem3_id}" not in node_ids

            # Depth 2: Should get all three
            response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{mem1_id}&depth=2")
            assert response.status_code == 200
            data = response.json()
            assert data["meta"]["depth"] == 2

            node_ids = {n["id"] for n in data["nodes"]}
            assert f"memory_{mem1_id}" in node_ids
            assert f"memory_{mem2_id}" in node_ids
            assert f"memory_{mem3_id}" in node_ids
        finally:
            # Restore original auto-link setting
            settings.MEMORY_NUM_AUTO_LINK = original_auto_link

    @pytest.mark.asyncio
    async def test_subgraph_cycle_detection(self, http_client):
        """Cycles in graph don't cause infinite loops."""
        # Create memories that form a cycle: A -> B -> C -> A
        mem_a = await http_client.post("/api/v1/memories", json={
            "title": "Cycle Node A",
            "content": "Node A in cycle",
            "context": "Testing cycle detection",
            "keywords": ["cycle_a"],
            "tags": ["cycle"],
            "importance": 7
        })
        mem_a_id = mem_a.json()["id"]

        mem_b = await http_client.post("/api/v1/memories", json={
            "title": "Cycle Node B",
            "content": "Node B in cycle",
            "context": "Testing cycle detection",
            "keywords": ["cycle_b"],
            "tags": ["cycle"],
            "importance": 7
        })
        mem_b_id = mem_b.json()["id"]

        mem_c = await http_client.post("/api/v1/memories", json={
            "title": "Cycle Node C",
            "content": "Node C in cycle",
            "context": "Testing cycle detection",
            "keywords": ["cycle_c"],
            "tags": ["cycle"],
            "importance": 7
        })
        mem_c_id = mem_c.json()["id"]

        # Create cycle: A -> B -> C -> A
        await http_client.post(f"/api/v1/memories/{mem_a_id}/links", json={
            "related_ids": [mem_b_id]
        })
        await http_client.post(f"/api/v1/memories/{mem_b_id}/links", json={
            "related_ids": [mem_c_id]
        })
        await http_client.post(f"/api/v1/memories/{mem_c_id}/links", json={
            "related_ids": [mem_a_id]
        })

        # Should complete without infinite loop, even with depth=3
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{mem_a_id}&depth=3")
        assert response.status_code == 200
        data = response.json()

        # Should have all three nodes, each appearing once
        node_ids = [n["id"] for n in data["nodes"]]
        assert f"memory_{mem_a_id}" in node_ids
        assert f"memory_{mem_b_id}" in node_ids
        assert f"memory_{mem_c_id}" in node_ids
        assert len(data["nodes"]) == 3  # No duplicates

    @pytest.mark.asyncio
    async def test_subgraph_node_types_filter(self, http_client):
        """node_types parameter filters which node types to include."""
        # Create memory and entity linked together
        mem_response = await http_client.post("/api/v1/memories", json={
            "title": "Filter Test Memory",
            "content": "Memory for filter test",
            "context": "Testing node_types filter",
            "keywords": ["filter"],
            "tags": ["filter-test"],
            "importance": 7
        })
        memory_id = mem_response.json()["id"]

        entity_response = await http_client.post("/api/v1/entities", json={
            "name": "Filter Test Entity",
            "entity_type": "Organization"
        })
        entity_id = entity_response.json()["id"]

        # Link entity to memory
        await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
            "memory_id": memory_id
        })

        # With node_types=memory only - should not traverse to entity
        response = await http_client.get(
            f"/api/v1/graph/subgraph?node_id=memory_{memory_id}&node_types=memory"
        )
        assert response.status_code == 200
        data = response.json()

        # Should only have the memory node
        entity_nodes = [n for n in data["nodes"] if n["type"] == "entity"]
        assert len(entity_nodes) == 0

        # With node_types=memory,entity - should traverse to entity
        response = await http_client.get(
            f"/api/v1/graph/subgraph?node_id=memory_{memory_id}&node_types=memory,entity"
        )
        assert response.status_code == 200
        data = response.json()

        entity_nodes = [n for n in data["nodes"] if n["type"] == "entity"]
        assert len(entity_nodes) >= 1

    @pytest.mark.asyncio
    async def test_subgraph_max_nodes_truncation(self, http_client):
        """max_nodes limit causes truncation with truncated flag set."""
        # Create multiple linked memories
        mem_ids = []
        for i in range(5):
            mem_response = await http_client.post("/api/v1/memories", json={
                "title": f"Truncation Test Memory {i}",
                "content": f"Memory {i} for truncation test",
                "context": "Testing max_nodes",
                "keywords": [f"truncation_{i}"],
                "tags": ["truncation"],
                "importance": 7
            })
            mem_ids.append(mem_response.json()["id"])

        # Link all to first
        for i in range(1, len(mem_ids)):
            await http_client.post(f"/api/v1/memories/{mem_ids[0]}/links", json={
                "related_ids": [mem_ids[i]]
            })

        # Request with very low max_nodes
        response = await http_client.get(
            f"/api/v1/graph/subgraph?node_id=memory_{mem_ids[0]}&max_nodes=2"
        )
        assert response.status_code == 200
        data = response.json()

        # Should respect max_nodes limit
        assert len(data["nodes"]) <= 2
        # Should indicate truncation
        assert data["meta"]["truncated"] is True

    @pytest.mark.asyncio
    async def test_subgraph_depth_field_on_nodes(self, http_client):
        """Each node has correct depth value."""
        # Create linked memories: Center -> Neighbor
        center_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Center",
            "content": "Center memory for depth test",
            "context": "Testing depth field",
            "keywords": ["depth_center"],
            "tags": ["depth"],
            "importance": 7
        })
        center_id = center_response.json()["id"]

        neighbor_response = await http_client.post("/api/v1/memories", json={
            "title": "Depth Neighbor",
            "content": "Neighbor memory for depth test",
            "context": "Testing depth field",
            "keywords": ["depth_neighbor"],
            "tags": ["depth"],
            "importance": 7
        })
        neighbor_id = neighbor_response.json()["id"]

        await http_client.post(f"/api/v1/memories/{center_id}/links", json={
            "related_ids": [neighbor_id]
        })

        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{center_id}")
        assert response.status_code == 200
        data = response.json()

        # Center should have depth 0
        center_node = next(n for n in data["nodes"] if n["id"] == f"memory_{center_id}")
        assert center_node["depth"] == 0

        # Neighbor should have depth 1
        neighbor_node = next(n for n in data["nodes"] if n["id"] == f"memory_{neighbor_id}")
        assert neighbor_node["depth"] == 1

    @pytest.mark.asyncio
    async def test_subgraph_all_edge_types(self, http_client):
        """Response includes all edge types: memory_link, entity_memory, entity_relationship."""
        # Create memories
        mem1 = await http_client.post("/api/v1/memories", json={
            "title": "Edge Test Memory 1",
            "content": "Memory 1 for edge test",
            "context": "Testing edge types",
            "keywords": ["edge1"],
            "tags": ["edges"],
            "importance": 7
        })
        mem1_id = mem1.json()["id"]

        mem2 = await http_client.post("/api/v1/memories", json={
            "title": "Edge Test Memory 2",
            "content": "Memory 2 for edge test",
            "context": "Testing edge types",
            "keywords": ["edge2"],
            "tags": ["edges"],
            "importance": 7
        })
        mem2_id = mem2.json()["id"]

        # Create entities
        ent1 = await http_client.post("/api/v1/entities", json={
            "name": "Edge Entity 1",
            "entity_type": "Individual"
        })
        ent1_id = ent1.json()["id"]

        ent2 = await http_client.post("/api/v1/entities", json={
            "name": "Edge Entity 2",
            "entity_type": "Individual"
        })
        ent2_id = ent2.json()["id"]

        # Create all edge types:
        # memory_link: mem1 <-> mem2
        await http_client.post(f"/api/v1/memories/{mem1_id}/links", json={
            "related_ids": [mem2_id]
        })

        # entity_memory: ent1 -> mem1
        await http_client.post(f"/api/v1/entities/{ent1_id}/memories", json={
            "memory_id": mem1_id
        })

        # entity_relationship: ent1 -> ent2
        await http_client.post(f"/api/v1/entities/{ent1_id}/relationships", json={
            "target_entity_id": ent2_id,
            "relationship_type": "knows"
        })

        # Link ent2 to mem2 to ensure both entities are in subgraph
        await http_client.post(f"/api/v1/entities/{ent2_id}/memories", json={
            "memory_id": mem2_id
        })

        # Get subgraph
        response = await http_client.get(
            f"/api/v1/graph/subgraph?node_id=memory_{mem1_id}&depth=2"
        )
        assert response.status_code == 200
        data = response.json()

        # Check edge types are present
        edge_types = {e["type"] for e in data["edges"]}
        assert "memory_link" in edge_types
        assert "entity_memory" in edge_types
        assert "entity_relationship" in edge_types

        # Check meta counts
        assert data["meta"]["memory_link_count"] >= 1
        assert data["meta"]["entity_memory_count"] >= 1
        assert data["meta"]["entity_relationship_count"] >= 1

    @pytest.mark.asyncio
    async def test_subgraph_invalid_node_id_format(self, http_client):
        """Returns 400 for invalid node_id format."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=invalid_format")
        assert response.status_code == 400
        assert "Invalid node_id format" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_subgraph_missing_node_id(self, http_client):
        """Returns 400 when node_id is not provided."""
        response = await http_client.get("/api/v1/graph/subgraph")
        assert response.status_code == 400
        assert "Missing required parameter" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_subgraph_nonexistent_memory(self, http_client):
        """Returns 404 for nonexistent memory."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=memory_99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_subgraph_nonexistent_entity(self, http_client):
        """Returns 404 for nonexistent entity."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=entity_99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_subgraph_invalid_depth(self, http_client):
        """Returns 400 for invalid depth parameter."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=memory_1&depth=not_a_number")
        assert response.status_code == 400
        assert "Invalid depth" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_subgraph_depth_below_minimum(self, http_client):
        """Returns 400 for depth < 1."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=memory_1&depth=0")
        assert response.status_code == 400
        assert "Must be at least 1" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_subgraph_invalid_node_types(self, http_client):
        """Returns 400 for invalid node_types parameter."""
        response = await http_client.get("/api/v1/graph/subgraph?node_id=memory_1&node_types=invalid")
        assert response.status_code == 400
        assert "Invalid node_types" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_subgraph_meta_includes_all_fields(self, http_client):
        """Meta object includes all expected fields."""
        mem_response = await http_client.post("/api/v1/memories", json={
            "title": "Meta Test Memory",
            "content": "Memory for meta test",
            "context": "Testing meta fields",
            "keywords": ["meta"],
            "tags": ["meta-test"],
            "importance": 7
        })
        memory_id = mem_response.json()["id"]

        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{memory_id}")
        assert response.status_code == 200
        data = response.json()

        meta = data["meta"]
        assert "center_node_id" in meta
        assert "depth" in meta
        assert "node_types" in meta
        assert "max_nodes" in meta
        assert "memory_count" in meta
        assert "entity_count" in meta
        assert "edge_count" in meta
        assert "memory_link_count" in meta
        assert "entity_relationship_count" in meta
        assert "entity_memory_count" in meta
        assert "truncated" in meta


class TestGraphNewNodeTypes:
    """Tests for project, document, and code_artifact node types in graph API."""

    @pytest.mark.asyncio
    async def test_graph_includes_project_nodes(self, http_client):
        """GET /api/v1/graph includes project nodes when projects exist."""
        # Create a project
        project_resp = await http_client.post("/api/v1/projects", json={
            "name": "Test Project",
            "description": "Project for graph test",
            "project_type": "development"
        })
        assert project_resp.status_code in [200, 201]
        project_id = project_resp.json()["id"]

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check project node exists
        project_nodes = [n for n in data["nodes"] if n["type"] == "project"]
        assert len(project_nodes) >= 1
        assert any(n["data"]["id"] == project_id for n in project_nodes)

        # Check meta includes project_count
        assert "project_count" in data["meta"]
        assert data["meta"]["project_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_includes_document_nodes(self, http_client):
        """GET /api/v1/graph includes document nodes when documents exist."""
        # Create a document
        doc_resp = await http_client.post("/api/v1/documents", json={
            "title": "Test Document",
            "description": "Document for graph test",
            "content": "This is the document content for testing graph API",
            "document_type": "text",
            "tags": ["test"]
        })
        assert doc_resp.status_code in [200, 201]
        document_id = doc_resp.json()["id"]

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check document node exists
        document_nodes = [n for n in data["nodes"] if n["type"] == "document"]
        assert len(document_nodes) >= 1
        assert any(n["data"]["id"] == document_id for n in document_nodes)

        # Check meta includes document_count
        assert "document_count" in data["meta"]
        assert data["meta"]["document_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_includes_code_artifact_nodes(self, http_client):
        """GET /api/v1/graph includes code_artifact nodes when artifacts exist."""
        # Create a code artifact
        artifact_resp = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Test Artifact",
            "description": "Code artifact for graph test",
            "code": "def hello(): return 'world'",
            "language": "python",
            "tags": ["test"]
        })
        assert artifact_resp.status_code in [200, 201]
        artifact_id = artifact_resp.json()["id"]

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check code_artifact node exists
        artifact_nodes = [n for n in data["nodes"] if n["type"] == "code_artifact"]
        assert len(artifact_nodes) >= 1
        assert any(n["data"]["id"] == artifact_id for n in artifact_nodes)

        # Check meta includes code_artifact_count
        assert "code_artifact_count" in data["meta"]
        assert data["meta"]["code_artifact_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_memory_project_edges(self, http_client):
        """Graph includes memory_project edges when memory linked to project."""
        # Create project
        project_resp = await http_client.post("/api/v1/projects", json={
            "name": "Edge Test Project",
            "description": "Project for edge test",
            "project_type": "development"
        })
        project_id = project_resp.json()["id"]

        # Create memory with project_ids
        await http_client.post("/api/v1/memories", json={
            "title": "Project Linked Memory",
            "content": "Memory linked to project",
            "context": "Testing memory_project edges",
            "keywords": ["project"],
            "tags": ["project-test"],
            "importance": 7,
            "project_ids": [project_id]
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check memory_project edge exists
        memory_project_edges = [e for e in data["edges"] if e["type"] == "memory_project"]
        assert len(memory_project_edges) >= 1

        # Check meta includes count
        assert "memory_project_count" in data["meta"]
        assert data["meta"]["memory_project_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_document_project_edges(self, http_client):
        """Graph includes document_project edges when document linked to project."""
        # Create project
        project_resp = await http_client.post("/api/v1/projects", json={
            "name": "Document Edge Project",
            "description": "Project for document edge test",
            "project_type": "development"
        })
        project_id = project_resp.json()["id"]

        # Create document with project_id
        await http_client.post("/api/v1/documents", json={
            "title": "Project Linked Document",
            "description": "Document linked to project",
            "content": "Document content for edge testing",
            "document_type": "text",
            "tags": ["test"],
            "project_id": project_id
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check document_project edge exists
        document_project_edges = [e for e in data["edges"] if e["type"] == "document_project"]
        assert len(document_project_edges) >= 1

        # Check meta includes count
        assert "document_project_count" in data["meta"]
        assert data["meta"]["document_project_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_code_artifact_project_edges(self, http_client):
        """Graph includes code_artifact_project edges when artifact linked to project."""
        # Create project
        project_resp = await http_client.post("/api/v1/projects", json={
            "name": "Artifact Edge Project",
            "description": "Project for artifact edge test",
            "project_type": "development"
        })
        project_id = project_resp.json()["id"]

        # Create code artifact with project_id
        await http_client.post("/api/v1/code-artifacts", json={
            "title": "Project Linked Artifact",
            "description": "Artifact linked to project",
            "code": "print('hello')",
            "language": "python",
            "tags": ["test"],
            "project_id": project_id
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check code_artifact_project edge exists
        artifact_project_edges = [e for e in data["edges"] if e["type"] == "code_artifact_project"]
        assert len(artifact_project_edges) >= 1

        # Check meta includes count
        assert "code_artifact_project_count" in data["meta"]
        assert data["meta"]["code_artifact_project_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_memory_document_edges(self, http_client):
        """Graph includes memory_document edges when memory linked to document."""
        # Create document
        doc_resp = await http_client.post("/api/v1/documents", json={
            "title": "Document for Memory Link",
            "description": "Document to be linked",
            "content": "Document content",
            "document_type": "text",
            "tags": ["test"]
        })
        document_id = doc_resp.json()["id"]

        # Create memory with document_ids
        await http_client.post("/api/v1/memories", json={
            "title": "Document Linked Memory",
            "content": "Memory linked to document",
            "context": "Testing memory_document edges",
            "keywords": ["document"],
            "tags": ["document-test"],
            "importance": 7,
            "document_ids": [document_id]
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check memory_document edge exists
        memory_document_edges = [e for e in data["edges"] if e["type"] == "memory_document"]
        assert len(memory_document_edges) >= 1

        # Check meta includes count
        assert "memory_document_count" in data["meta"]
        assert data["meta"]["memory_document_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_memory_code_artifact_edges(self, http_client):
        """Graph includes memory_code_artifact edges when memory linked to artifact."""
        # Create code artifact
        artifact_resp = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Artifact for Memory Link",
            "description": "Artifact to be linked",
            "code": "x = 1",
            "language": "python",
            "tags": ["test"]
        })
        artifact_id = artifact_resp.json()["id"]

        # Create memory with code_artifact_ids
        await http_client.post("/api/v1/memories", json={
            "title": "Artifact Linked Memory",
            "content": "Memory linked to artifact",
            "context": "Testing memory_code_artifact edges",
            "keywords": ["artifact"],
            "tags": ["artifact-test"],
            "importance": 7,
            "code_artifact_ids": [artifact_id]
        })

        # Get graph
        response = await http_client.get("/api/v1/graph")
        assert response.status_code == 200
        data = response.json()

        # Check memory_code_artifact edge exists
        memory_artifact_edges = [e for e in data["edges"] if e["type"] == "memory_code_artifact"]
        assert len(memory_artifact_edges) >= 1

        # Check meta includes count
        assert "memory_code_artifact_count" in data["meta"]
        assert data["meta"]["memory_code_artifact_count"] >= 1

    @pytest.mark.asyncio
    async def test_graph_node_types_filter_excludes_projects(self, http_client):
        """node_types parameter can exclude project nodes."""
        # Create a project
        await http_client.post("/api/v1/projects", json={
            "name": "Filter Test Project",
            "description": "Project for filter test",
            "project_type": "development"
        })

        # Get graph without projects
        response = await http_client.get("/api/v1/graph?node_types=memory,entity")
        assert response.status_code == 200
        data = response.json()

        # Should have no project nodes
        project_nodes = [n for n in data["nodes"] if n["type"] == "project"]
        assert len(project_nodes) == 0

    @pytest.mark.asyncio
    async def test_subgraph_from_project_center(self, http_client):
        """Subgraph can be centered on a project node."""
        # Create project
        project_resp = await http_client.post("/api/v1/projects", json={
            "name": "Center Project",
            "description": "Project to center subgraph on",
            "project_type": "development"
        })
        project_id = project_resp.json()["id"]

        # Create memory linked to project
        await http_client.post("/api/v1/memories", json={
            "title": "Project Related Memory",
            "content": "Memory for project subgraph test",
            "context": "Testing subgraph from project center",
            "keywords": ["project"],
            "tags": ["test"],
            "importance": 7,
            "project_ids": [project_id]
        })

        # Get subgraph centered on project
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=project_{project_id}")
        assert response.status_code == 200
        data = response.json()

        # Center should be the project
        assert data["meta"]["center_node_id"] == f"project_{project_id}"

        # Should include the linked memory
        memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
        assert len(memory_nodes) >= 1

    @pytest.mark.asyncio
    async def test_subgraph_from_document_center(self, http_client):
        """Subgraph can be centered on a document node."""
        # Create document
        doc_resp = await http_client.post("/api/v1/documents", json={
            "title": "Center Document",
            "description": "Document to center subgraph on",
            "content": "Document content for subgraph test",
            "document_type": "text",
            "tags": ["test"]
        })
        document_id = doc_resp.json()["id"]

        # Create memory linked to document
        await http_client.post("/api/v1/memories", json={
            "title": "Document Related Memory",
            "content": "Memory for document subgraph test",
            "context": "Testing subgraph from document center",
            "keywords": ["document"],
            "tags": ["test"],
            "importance": 7,
            "document_ids": [document_id]
        })

        # Get subgraph centered on document
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=document_{document_id}")
        assert response.status_code == 200
        data = response.json()

        # Center should be the document
        assert data["meta"]["center_node_id"] == f"document_{document_id}"

        # Should include the linked memory
        memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
        assert len(memory_nodes) >= 1

    @pytest.mark.asyncio
    async def test_subgraph_from_code_artifact_center(self, http_client):
        """Subgraph can be centered on a code_artifact node."""
        # Create code artifact
        artifact_resp = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Center Artifact",
            "description": "Artifact to center subgraph on",
            "code": "result = 42",
            "language": "python",
            "tags": ["test"]
        })
        artifact_id = artifact_resp.json()["id"]

        # Create memory linked to artifact
        await http_client.post("/api/v1/memories", json={
            "title": "Artifact Related Memory",
            "content": "Memory for artifact subgraph test",
            "context": "Testing subgraph from artifact center",
            "keywords": ["artifact"],
            "tags": ["test"],
            "importance": 7,
            "code_artifact_ids": [artifact_id]
        })

        # Get subgraph centered on artifact
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=code_artifact_{artifact_id}")
        assert response.status_code == 200
        data = response.json()

        # Center should be the code artifact
        assert data["meta"]["center_node_id"] == f"code_artifact_{artifact_id}"

        # Should include the linked memory
        memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
        assert len(memory_nodes) >= 1

    @pytest.mark.asyncio
    async def test_subgraph_meta_includes_new_counts(self, http_client):
        """Subgraph meta includes counts for all new node and edge types."""
        # Create memory for starting point
        mem_resp = await http_client.post("/api/v1/memories", json={
            "title": "Meta Test Memory",
            "content": "Memory for meta fields test",
            "context": "Testing new meta fields",
            "keywords": ["meta"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = mem_resp.json()["id"]

        # Get subgraph
        response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{memory_id}")
        assert response.status_code == 200
        data = response.json()

        meta = data["meta"]

        # Check new node count fields exist
        assert "project_count" in meta
        assert "document_count" in meta
        assert "code_artifact_count" in meta

        # Check new edge count fields exist
        assert "memory_project_count" in meta
        assert "document_project_count" in meta
        assert "code_artifact_project_count" in meta
        assert "memory_document_count" in meta
        assert "memory_code_artifact_count" in meta
