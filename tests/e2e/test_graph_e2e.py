"""
End-to-end tests for Graph REST API endpoints with PostgreSQL backend.

Tests the /api/v1/graph endpoints with real PostgreSQL database and pgvector
to validate CTE traversal, all 5 node types, and 8 edge types.

Requires:
- PostgreSQL with pgvector running in Docker
- In-process FastMCP server (provided by conftest fixtures)
"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.e2e
async def test_graph_empty_returns_200(http_client):
    """GET /api/v1/graph returns empty graph initially."""
    response = await http_client.get("/api/v1/graph")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert "meta" in data


@pytest.mark.e2e
async def test_graph_with_all_node_types(http_client):
    """GET /api/v1/graph returns all 5 node types: memory, entity, project, document, code_artifact."""
    # Create a project
    project_resp = await http_client.post("/api/v1/projects", json={
        "name": "E2E Test Project",
        "description": "Project for PostgreSQL E2E graph test",
        "project_type": "development"
    })
    assert project_resp.status_code in [200, 201]
    project_id = project_resp.json()["id"]

    # Create a document linked to project
    doc_resp = await http_client.post("/api/v1/documents", json={
        "title": "E2E Test Document",
        "description": "Document for PostgreSQL E2E graph test",
        "content": "This is test document content for PostgreSQL graph E2E testing.",
        "document_type": "text",
        "tags": ["e2e-test"],
        "project_id": project_id
    })
    assert doc_resp.status_code in [200, 201]
    document_id = doc_resp.json()["id"]

    # Create a code artifact linked to project
    artifact_resp = await http_client.post("/api/v1/code-artifacts", json={
        "title": "E2E Test Artifact",
        "description": "Artifact for PostgreSQL E2E graph test",
        "code": "def e2e_test(): return 'PostgreSQL'",
        "language": "python",
        "tags": ["e2e-test"],
        "project_id": project_id
    })
    assert artifact_resp.status_code in [200, 201]
    artifact_id = artifact_resp.json()["id"]

    # Create a memory linked to project, document, and artifact
    mem_resp = await http_client.post("/api/v1/memories", json={
        "title": "E2E Test Memory",
        "content": "Memory linked to project, document, and artifact for PostgreSQL E2E test",
        "context": "Testing PostgreSQL graph API",
        "keywords": ["e2e", "postgresql", "graph"],
        "tags": ["e2e-test"],
        "importance": 8,
        "project_ids": [project_id],
        "document_ids": [document_id],
        "code_artifact_ids": [artifact_id]
    })
    assert mem_resp.status_code in [200, 201]
    memory_id = mem_resp.json()["id"]

    # Create an entity
    entity_resp = await http_client.post("/api/v1/entities", json={
        "name": "E2E Test Entity",
        "entity_type": "Organization",
        "notes": "Entity for PostgreSQL E2E graph test"
    })
    assert entity_resp.status_code in [200, 201]
    entity_id = entity_resp.json()["id"]

    # Link entity to memory
    await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
        "memory_id": memory_id
    })

    # Get full graph
    response = await http_client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()

    # Verify all 5 node types are present
    node_types = {n["type"] for n in data["nodes"]}
    assert "memory" in node_types
    assert "entity" in node_types
    assert "project" in node_types
    assert "document" in node_types
    assert "code_artifact" in node_types

    # Verify all new edge types are present
    edge_types = {e["type"] for e in data["edges"]}
    assert "memory_project" in edge_types
    assert "document_project" in edge_types
    assert "code_artifact_project" in edge_types
    assert "memory_document" in edge_types
    assert "memory_code_artifact" in edge_types
    assert "entity_memory" in edge_types

    # Verify meta includes all counts
    meta = data["meta"]
    assert meta["memory_count"] >= 1
    assert meta["entity_count"] >= 1
    assert meta["project_count"] >= 1
    assert meta["document_count"] >= 1
    assert meta["code_artifact_count"] >= 1


@pytest.mark.e2e
async def test_graph_node_types_filter(http_client):
    """GET /api/v1/graph?node_types=memory,entity returns only specified types."""
    # Create a project (should be excluded when filtering)
    await http_client.post("/api/v1/projects", json={
        "name": "Filtered Project",
        "description": "Should be excluded",
        "project_type": "development"
    })

    # Create a memory
    await http_client.post("/api/v1/memories", json={
        "title": "Filtered Memory",
        "content": "Should be included",
        "context": "Testing filter",
        "keywords": ["filter"],
        "tags": ["test"],
        "importance": 7
    })

    # Get graph with filter
    response = await http_client.get("/api/v1/graph?node_types=memory,entity")
    assert response.status_code == 200
    data = response.json()

    # Should not have project nodes
    project_nodes = [n for n in data["nodes"] if n["type"] == "project"]
    assert len(project_nodes) == 0


@pytest.mark.e2e
async def test_subgraph_from_memory_center(http_client):
    """GET /api/v1/graph/subgraph?node_id=memory_X traverses from memory."""
    # Create a memory
    mem_resp = await http_client.post("/api/v1/memories", json={
        "title": "Subgraph Center Memory",
        "content": "Memory at the center of PostgreSQL subgraph",
        "context": "Testing PostgreSQL CTE subgraph",
        "keywords": ["subgraph", "postgresql"],
        "tags": ["e2e-test"],
        "importance": 8
    })
    assert mem_resp.status_code in [200, 201]
    memory_id = mem_resp.json()["id"]

    # Get subgraph
    response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{memory_id}")
    if response.status_code != 200:
        print(f"ERROR Response: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "nodes" in data
    assert "edges" in data
    assert "meta" in data
    assert data["meta"]["center_node_id"] == f"memory_{memory_id}"

    # Center node should have depth 0
    center_node = next(n for n in data["nodes"] if n["id"] == f"memory_{memory_id}")
    assert center_node["depth"] == 0


@pytest.mark.e2e
async def test_subgraph_from_project_center(http_client):
    """GET /api/v1/graph/subgraph?node_id=project_X traverses from project."""
    # Create project
    project_resp = await http_client.post("/api/v1/projects", json={
        "name": "Subgraph Center Project",
        "description": "Project at center of subgraph",
        "project_type": "development"
    })
    assert project_resp.status_code in [200, 201]
    project_id = project_resp.json()["id"]

    # Create memory linked to project
    await http_client.post("/api/v1/memories", json={
        "title": "Project Linked Memory",
        "content": "Memory linked to project for subgraph test",
        "context": "Testing project center subgraph",
        "keywords": ["project", "subgraph"],
        "tags": ["e2e-test"],
        "importance": 7,
        "project_ids": [project_id]
    })

    # Get subgraph centered on project
    response = await http_client.get(f"/api/v1/graph/subgraph?node_id=project_{project_id}")
    assert response.status_code == 200
    data = response.json()

    # Center should be the project
    assert data["meta"]["center_node_id"] == f"project_{project_id}"

    # Should include linked memory via traversal
    memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
    assert len(memory_nodes) >= 1


@pytest.mark.e2e
async def test_subgraph_from_document_center(http_client):
    """GET /api/v1/graph/subgraph?node_id=document_X traverses from document."""
    # Create document
    doc_resp = await http_client.post("/api/v1/documents", json={
        "title": "Subgraph Center Document",
        "description": "Document at center of subgraph",
        "content": "Document content for PostgreSQL subgraph test",
        "document_type": "text",
        "tags": ["e2e-test"]
    })
    assert doc_resp.status_code in [200, 201]
    document_id = doc_resp.json()["id"]

    # Create memory linked to document
    await http_client.post("/api/v1/memories", json={
        "title": "Document Linked Memory",
        "content": "Memory linked to document for subgraph test",
        "context": "Testing document center subgraph",
        "keywords": ["document", "subgraph"],
        "tags": ["e2e-test"],
        "importance": 7,
        "document_ids": [document_id]
    })

    # Get subgraph centered on document
    response = await http_client.get(f"/api/v1/graph/subgraph?node_id=document_{document_id}")
    assert response.status_code == 200
    data = response.json()

    # Center should be the document
    assert data["meta"]["center_node_id"] == f"document_{document_id}"

    # Should include linked memory via traversal
    memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
    assert len(memory_nodes) >= 1


@pytest.mark.e2e
async def test_subgraph_from_code_artifact_center(http_client):
    """GET /api/v1/graph/subgraph?node_id=code_artifact_X traverses from artifact."""
    # Create code artifact
    artifact_resp = await http_client.post("/api/v1/code-artifacts", json={
        "title": "Subgraph Center Artifact",
        "description": "Artifact at center of subgraph",
        "code": "print('PostgreSQL E2E')",
        "language": "python",
        "tags": ["e2e-test"]
    })
    assert artifact_resp.status_code in [200, 201]
    artifact_id = artifact_resp.json()["id"]

    # Create memory linked to artifact
    await http_client.post("/api/v1/memories", json={
        "title": "Artifact Linked Memory",
        "content": "Memory linked to artifact for subgraph test",
        "context": "Testing artifact center subgraph",
        "keywords": ["artifact", "subgraph"],
        "tags": ["e2e-test"],
        "importance": 7,
        "code_artifact_ids": [artifact_id]
    })

    # Get subgraph centered on artifact
    response = await http_client.get(f"/api/v1/graph/subgraph?node_id=code_artifact_{artifact_id}")
    assert response.status_code == 200
    data = response.json()

    # Center should be the code artifact
    assert data["meta"]["center_node_id"] == f"code_artifact_{artifact_id}"

    # Should include linked memory via traversal
    memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
    assert len(memory_nodes) >= 1


@pytest.mark.e2e
async def test_subgraph_cycle_detection_postgresql(http_client):
    """PostgreSQL CTE handles cycles without infinite loops (uses ARRAY cycle detection)."""
    # Create memories that form a cycle: A -> B -> C -> A
    mem_a_resp = await http_client.post("/api/v1/memories", json={
        "title": "Cycle Node A PostgreSQL",
        "content": "Node A in cycle for PostgreSQL CTE test",
        "context": "Testing PostgreSQL cycle detection",
        "keywords": ["cycle_a_pg"],
        "tags": ["cycle-test"],
        "importance": 7
    })
    mem_a_id = mem_a_resp.json()["id"]

    mem_b_resp = await http_client.post("/api/v1/memories", json={
        "title": "Cycle Node B PostgreSQL",
        "content": "Node B in cycle for PostgreSQL CTE test",
        "context": "Testing PostgreSQL cycle detection",
        "keywords": ["cycle_b_pg"],
        "tags": ["cycle-test"],
        "importance": 7
    })
    mem_b_id = mem_b_resp.json()["id"]

    mem_c_resp = await http_client.post("/api/v1/memories", json={
        "title": "Cycle Node C PostgreSQL",
        "content": "Node C in cycle for PostgreSQL CTE test",
        "context": "Testing PostgreSQL cycle detection",
        "keywords": ["cycle_c_pg"],
        "tags": ["cycle-test"],
        "importance": 7
    })
    mem_c_id = mem_c_resp.json()["id"]

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

    # Should have all three cycle nodes, each appearing exactly once (no duplicates)
    node_ids = [n["id"] for n in data["nodes"]]
    assert f"memory_{mem_a_id}" in node_ids
    assert f"memory_{mem_b_id}" in node_ids
    assert f"memory_{mem_c_id}" in node_ids

    # Each cycle node should appear exactly once (cycle detection prevents duplicates)
    cycle_node_ids = {f"memory_{mem_a_id}", f"memory_{mem_b_id}", f"memory_{mem_c_id}"}
    cycle_nodes_found = [n for n in data["nodes"] if n["id"] in cycle_node_ids]
    assert len(cycle_nodes_found) == 3, f"Expected 3 unique cycle nodes, found {len(cycle_nodes_found)}"

    # Verify no duplicate IDs overall (cycle detection working)
    assert len(node_ids) == len(set(node_ids)), "Duplicate node IDs found - cycle detection failed"


@pytest.mark.e2e
async def test_subgraph_multi_hop_traversal(http_client):
    """Subgraph traverses through multiple node types: Project -> Memory -> Entity."""
    # Create project
    project_resp = await http_client.post("/api/v1/projects", json={
        "name": "Multi-Hop Project",
        "description": "Project for multi-hop traversal test",
        "project_type": "development"
    })
    project_id = project_resp.json()["id"]

    # Create memory linked to project
    mem_resp = await http_client.post("/api/v1/memories", json={
        "title": "Multi-Hop Memory",
        "content": "Memory linked to project for multi-hop test",
        "context": "Testing multi-hop traversal",
        "keywords": ["multi-hop"],
        "tags": ["e2e-test"],
        "importance": 7,
        "project_ids": [project_id]
    })
    memory_id = mem_resp.json()["id"]

    # Create entity linked to memory
    entity_resp = await http_client.post("/api/v1/entities", json={
        "name": "Multi-Hop Entity",
        "entity_type": "Individual",
        "notes": "Entity for multi-hop test"
    })
    entity_id = entity_resp.json()["id"]

    await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
        "memory_id": memory_id
    })

    # Start from project, should reach entity via project -> memory -> entity
    response = await http_client.get(
        f"/api/v1/graph/subgraph?node_id=project_{project_id}&depth=2"
    )
    assert response.status_code == 200
    data = response.json()

    # Should have all three node types
    node_types = {n["type"] for n in data["nodes"]}
    assert "project" in node_types
    assert "memory" in node_types
    assert "entity" in node_types

    # Entity should be at depth 2 (project -> memory -> entity)
    entity_node = next(n for n in data["nodes"] if n["type"] == "entity")
    assert entity_node["depth"] == 2


@pytest.mark.e2e
async def test_subgraph_meta_includes_all_new_counts(http_client):
    """Subgraph meta includes counts for all 5 node types and 8 edge types."""
    # Create memory
    mem_resp = await http_client.post("/api/v1/memories", json={
        "title": "Meta Fields Test Memory",
        "content": "Memory for meta fields test",
        "context": "Testing meta fields",
        "keywords": ["meta"],
        "tags": ["e2e-test"],
        "importance": 7
    })
    memory_id = mem_resp.json()["id"]

    # Get subgraph
    response = await http_client.get(f"/api/v1/graph/subgraph?node_id=memory_{memory_id}")
    assert response.status_code == 200
    data = response.json()

    meta = data["meta"]

    # Node count fields
    assert "memory_count" in meta
    assert "entity_count" in meta
    assert "project_count" in meta
    assert "document_count" in meta
    assert "code_artifact_count" in meta

    # Edge count fields
    assert "memory_link_count" in meta
    assert "entity_relationship_count" in meta
    assert "entity_memory_count" in meta
    assert "memory_project_count" in meta
    assert "document_project_count" in meta
    assert "code_artifact_project_count" in meta
    assert "memory_document_count" in meta
    assert "memory_code_artifact_count" in meta

    # Other meta fields
    assert "center_node_id" in meta
    assert "depth" in meta
    assert "node_types" in meta
    assert "max_nodes" in meta
    assert "truncated" in meta


@pytest.mark.e2e
async def test_subgraph_node_types_filter_postgresql(http_client):
    """node_types filter controls which types are traversed in PostgreSQL CTE."""
    # Create memory and project linked together
    project_resp = await http_client.post("/api/v1/projects", json={
        "name": "Filter Test Project PG",
        "description": "Project for filter test",
        "project_type": "development"
    })
    project_id = project_resp.json()["id"]

    mem_resp = await http_client.post("/api/v1/memories", json={
        "title": "Filter Test Memory PG",
        "content": "Memory for filter test",
        "context": "Testing filter",
        "keywords": ["filter"],
        "tags": ["e2e-test"],
        "importance": 7,
        "project_ids": [project_id]
    })
    memory_id = mem_resp.json()["id"]

    # With node_types=memory only - should not traverse to project
    response = await http_client.get(
        f"/api/v1/graph/subgraph?node_id=memory_{memory_id}&node_types=memory"
    )
    assert response.status_code == 200
    data = response.json()

    # Should only have the memory node
    project_nodes = [n for n in data["nodes"] if n["type"] == "project"]
    assert len(project_nodes) == 0

    # With node_types=memory,project - should traverse to project
    response = await http_client.get(
        f"/api/v1/graph/subgraph?node_id=memory_{memory_id}&node_types=memory,project"
    )
    assert response.status_code == 200
    data = response.json()

    project_nodes = [n for n in data["nodes"] if n["type"] == "project"]
    assert len(project_nodes) >= 1


@pytest.mark.e2e
async def test_graph_pagination_with_offset(http_client):
    """GET /api/v1/graph supports pagination with offset parameter."""
    # Create multiple memories
    for i in range(5):
        await http_client.post("/api/v1/memories", json={
            "title": f"Pagination E2E Memory {i}",
            "content": f"Memory {i} for pagination E2E test",
            "context": "Testing pagination offset",
            "keywords": [f"pagination_e2e_{i}"],
            "tags": ["pagination-e2e"],
            "importance": 7
        })

    # Get first 2 memories
    response1 = await http_client.get("/api/v1/graph?limit=2&offset=0")
    assert response1.status_code == 200
    data1 = response1.json()
    first_page_ids = {n["id"] for n in data1["nodes"] if n["type"] == "memory"}

    # Get next 2 memories
    response2 = await http_client.get("/api/v1/graph?limit=2&offset=2")
    assert response2.status_code == 200
    data2 = response2.json()
    second_page_ids = {n["id"] for n in data2["nodes"] if n["type"] == "memory"}

    # Pages should not overlap
    assert first_page_ids.isdisjoint(second_page_ids)


@pytest.mark.e2e
async def test_graph_pagination_metadata(http_client):
    """GET /api/v1/graph includes pagination metadata in response."""
    # Create memories to test pagination metadata
    for i in range(5):
        await http_client.post("/api/v1/memories", json={
            "title": f"Pagination Meta E2E {i}",
            "content": f"Memory {i} for pagination meta E2E test",
            "context": "Testing pagination metadata",
            "keywords": [f"meta_e2e_{i}"],
            "tags": ["meta-e2e"],
            "importance": 7
        })

    # Get first page
    response = await http_client.get("/api/v1/graph?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()

    # Check pagination metadata
    meta = data["meta"]
    assert "total_memory_count" in meta
    assert "offset" in meta
    assert "limit" in meta
    assert "has_more" in meta

    assert meta["offset"] == 0
    assert meta["limit"] == 2
    assert meta["total_memory_count"] >= 5
    assert meta["has_more"] is True  # We have more than 2 memories


@pytest.mark.e2e
async def test_graph_sort_by_importance(http_client):
    """GET /api/v1/graph sorts by importance when specified."""
    # Create memories with different importance levels
    await http_client.post("/api/v1/memories", json={
        "title": "Low Importance E2E",
        "content": "Memory with low importance for E2E test",
        "context": "Testing sort by importance",
        "keywords": ["low_importance_e2e"],
        "tags": ["sort-e2e"],
        "importance": 3
    })
    await http_client.post("/api/v1/memories", json={
        "title": "High Importance E2E",
        "content": "Memory with high importance for E2E test",
        "context": "Testing sort by importance",
        "keywords": ["high_importance_e2e"],
        "tags": ["sort-e2e"],
        "importance": 10
    })

    # Sort by importance descending
    response = await http_client.get("/api/v1/graph?sort_by=importance&sort_order=desc&limit=2")
    assert response.status_code == 200
    data = response.json()

    memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
    if len(memory_nodes) >= 2:
        # First memory should have higher or equal importance
        assert memory_nodes[0]["data"]["importance"] >= memory_nodes[1]["data"]["importance"]


@pytest.mark.e2e
async def test_graph_invalid_pagination_params(http_client):
    """GET /api/v1/graph returns 400 for invalid pagination parameters."""
    # Invalid offset
    response = await http_client.get("/api/v1/graph?offset=not_a_number")
    assert response.status_code == 400
    assert "Invalid offset" in response.json()["error"]

    # Negative offset
    response = await http_client.get("/api/v1/graph?offset=-1")
    assert response.status_code == 400
    assert "non-negative" in response.json()["error"]

    # Invalid sort_by
    response = await http_client.get("/api/v1/graph?sort_by=invalid_field")
    assert response.status_code == 400
    assert "sort_by must be one of" in response.json()["error"]

    # Invalid sort_order
    response = await http_client.get("/api/v1/graph?sort_order=invalid")
    assert response.status_code == 400
    assert "sort_order must be one of" in response.json()["error"]


@pytest.mark.e2e
async def test_graph_offset_beyond_total(http_client):
    """GET /api/v1/graph returns empty results when offset exceeds total."""
    response = await http_client.get("/api/v1/graph?offset=99999")
    assert response.status_code == 200
    data = response.json()

    # Should have no memory nodes since offset is beyond total
    memory_nodes = [n for n in data["nodes"] if n["type"] == "memory"]
    assert len(memory_nodes) == 0

    # Metadata should still be present
    assert data["meta"]["has_more"] is False
