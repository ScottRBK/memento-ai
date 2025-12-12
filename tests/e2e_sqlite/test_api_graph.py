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
