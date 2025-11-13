"""
E2E tests for entity MCP tools with real PostgreSQL database
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_basic_e2e(docker_services, mcp_server_url):
    """Test creating an entity with all fields"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("create_entity", {
            "name": "Acme Corporation",
            "entity_type": "Organization",
            "notes": "A leading software company",
            "tags": ["tech", "b2b", "enterprise"]
        })

        assert result.data is not None
        assert result.data.id is not None
        assert result.data.name == "Acme Corporation"
        assert result.data.entity_type == "Organization"
        assert result.data.notes == "A leading software company"
        assert result.data.tags == ["tech", "b2b", "enterprise"]
        assert result.data.created_at is not None
        assert result.data.updated_at is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_with_custom_type_e2e(docker_services, mcp_server_url):
    """Test creating entity with custom type"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("create_entity", {
            "name": "Temperature Sensor A1",
            "entity_type": "Other",
            "custom_type": "IoT Sensor",
            "notes": "Temperature monitoring device",
            "tags": ["hardware", "iot"]
        })

        assert result.data is not None
        assert result.data.entity_type == "Other"
        assert result.data.custom_type == "IoT Sensor"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_e2e(docker_services, mcp_server_url):
    """Test creating then retrieving an entity"""
    async with Client(mcp_server_url) as client:
        # Create entity
        create_result = await client.call_tool("create_entity", {
            "name": "Test Entity",
            "entity_type": "Individual",
            "tags": ["test"]
        })

        entity_id = create_result.data.id

        # Get entity
        get_result = await client.call_tool("get_entity", {
            "entity_id": entity_id
        })

        assert get_result.data is not None
        assert get_result.data.id == entity_id
        assert get_result.data.name == "Test Entity"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_e2e(docker_services, mcp_server_url):
    """Test listing entities"""
    async with Client(mcp_server_url) as client:
        # Create multiple entities
        entity_names = ["entity-list-1", "entity-list-2", "entity-list-3"]

        for name in entity_names:
            await client.call_tool("create_entity", {
                "name": name,
                "entity_type": "Organization",
                "tags": ["list-test"]
            })

        # List all entities
        list_result = await client.call_tool("list_entities", {})

        assert list_result.data is not None
        assert "entities" in list_result.data
        assert "total_count" in list_result.data

        entities = list_result.data["entities"]
        assert len(entities) >= 3

        # Verify our entities are in the list
        entity_names_in_result = [e["name"] for e in entities]
        for name in entity_names:
            assert name in entity_names_in_result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_filter_by_type_e2e(docker_services, mcp_server_url):
    """Test filtering entities by type"""
    async with Client(mcp_server_url) as client:
        # Create entities of different types
        await client.call_tool("create_entity", {
            "name": "Test Company",
            "entity_type": "Organization",
            "tags": ["filter-test"]
        })

        await client.call_tool("create_entity", {
            "name": "Test Person",
            "entity_type": "Individual",
            "tags": ["filter-test"]
        })

        # Filter by Organization
        list_result = await client.call_tool("list_entities", {
            "entity_type": "Organization"
        })

        entities = list_result.data["entities"]
        # Should have at least our test org
        org_entities = [e for e in entities if "filter-test" in e["tags"]]
        assert len(org_entities) >= 1
        assert all(e["entity_type"] == "Organization" for e in org_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_filter_by_tags_e2e(docker_services, mcp_server_url):
    """Test filtering entities by tags"""
    async with Client(mcp_server_url) as client:
        # Create entities with different tags
        await client.call_tool("create_entity", {
            "name": "Engineering Team",
            "entity_type": "Team",
            "tags": ["engineering", "tag-filter-test"]
        })

        await client.call_tool("create_entity", {
            "name": "Sales Team",
            "entity_type": "Team",
            "tags": ["sales", "tag-filter-test"]
        })

        # Filter by engineering tag
        list_result = await client.call_tool("list_entities", {
            "tags": ["engineering"]
        })

        entities = list_result.data["entities"]
        eng_entities = [e for e in entities if "tag-filter-test" in e["tags"]]
        assert len(eng_entities) >= 1
        assert all("engineering" in e["tags"] for e in eng_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_e2e(docker_services, mcp_server_url):
    """Test updating an entity (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create entity
        create_result = await client.call_tool("create_entity", {
            "name": "Original Name",
            "entity_type": "Organization",
            "notes": "Original notes",
            "tags": ["original"]
        })

        entity_id = create_result.data.id

        # Update only name and notes
        update_result = await client.call_tool("update_entity", {
            "entity_id": entity_id,
            "name": "Updated Name",
            "notes": "Updated notes"
        })

        assert update_result.data.name == "Updated Name"
        assert update_result.data.notes == "Updated notes"
        assert update_result.data.tags == ["original"]  # Unchanged


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_entity_e2e(docker_services, mcp_server_url):
    """Test deleting an entity"""
    async with Client(mcp_server_url) as client:
        # Create entity
        create_result = await client.call_tool("create_entity", {
            "name": "To Delete",
            "entity_type": "Organization",
            "tags": []
        })

        entity_id = create_result.data.id

        # Delete entity
        delete_result = await client.call_tool("delete_entity", {
            "entity_id": entity_id
        })

        assert delete_result.data is not None
        assert delete_result.data["deleted_id"] == entity_id

        # Verify entity is gone
        try:
            await client.call_tool("get_entity", {
                "entity_id": entity_id
            })
            assert False, "Expected error for deleted entity"
        except Exception as e:
            assert "not found" in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_link_entity_to_memory_e2e(docker_services, mcp_server_url):
    """Test linking entity to memory"""
    async with Client(mcp_server_url) as client:
        # Create entity
        entity_result = await client.call_tool("create_entity", {
            "name": "Test Entity",
            "entity_type": "Organization",
            "tags": []
        })
        entity_id = entity_result.data.id

        # Create memory
        memory_result = await client.call_tool("create_memory", {
            "title": "Test Memory",
            "content": "Memory for linking test",
            "context": "Testing entity-memory linking",
            "keywords": ["test"],
            "tags": [],
            "importance": 7
        })
        memory_id = memory_result.data.id

        # Link entity to memory
        link_result = await client.call_tool("link_entity_to_memory", {
            "entity_id": entity_id,
            "memory_id": memory_id
        })

        assert link_result.data is not None
        assert link_result.data["success"] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_unlink_entity_from_memory_e2e(docker_services, mcp_server_url):
    """Test unlinking entity from memory"""
    async with Client(mcp_server_url) as client:
        # Create entity and memory
        entity_result = await client.call_tool("create_entity", {
            "name": "Test Entity",
            "entity_type": "Organization",
            "tags": []
        })
        entity_id = entity_result.data.id

        memory_result = await client.call_tool("create_memory", {
            "title": "Test Memory",
            "content": "Memory for unlink test",
            "context": "Testing entity-memory unlinking",
            "keywords": ["test"],
            "tags": [],
            "importance": 7
        })
        memory_id = memory_result.data.id

        # Link first
        await client.call_tool("link_entity_to_memory", {
            "entity_id": entity_id,
            "memory_id": memory_id
        })

        # Unlink
        unlink_result = await client.call_tool("unlink_entity_from_memory", {
            "entity_id": entity_id,
            "memory_id": memory_id
        })

        assert unlink_result.data is not None
        assert unlink_result.data["success"] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test creating relationship between entities"""
    async with Client(mcp_server_url) as client:
        # Create two entities
        entity1_result = await client.call_tool("create_entity", {
            "name": "Company A",
            "entity_type": "Organization",
            "tags": []
        })
        entity1_id = entity1_result.data.id

        entity2_result = await client.call_tool("create_entity", {
            "name": "Person B",
            "entity_type": "Individual",
            "tags": []
        })
        entity2_id = entity2_result.data.id

        # Create relationship
        rel_result = await client.call_tool("create_entity_relationship", {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "relationship_type": "employs",
            "strength": 0.9,
            "confidence": 0.85,
            "metadata": {"role": "engineer", "department": "R&D"}
        })

        assert rel_result.data is not None
        assert rel_result.data.id is not None
        assert rel_result.data.source_entity_id == entity1_id
        assert rel_result.data.target_entity_id == entity2_id
        assert rel_result.data.relationship_type == "employs"
        assert rel_result.data.strength == 0.9
        assert rel_result.data.confidence == 0.85
        assert rel_result.data.metadata == {"role": "engineer", "department": "R&D"}


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_relationships_e2e(docker_services, mcp_server_url):
    """Test retrieving entity relationships"""
    async with Client(mcp_server_url) as client:
        # Create entities
        entity1_result = await client.call_tool("create_entity", {
            "name": "Org X",
            "entity_type": "Organization",
            "tags": []
        })
        entity1_id = entity1_result.data.id

        entity2_result = await client.call_tool("create_entity", {
            "name": "Person Y",
            "entity_type": "Individual",
            "tags": []
        })
        entity2_id = entity2_result.data.id

        # Create relationship
        await client.call_tool("create_entity_relationship", {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "relationship_type": "collaborates_with"
        })

        # Get relationships
        rel_result = await client.call_tool("get_entity_relationships", {
            "entity_id": entity1_id
        })

        assert rel_result.data is not None
        assert "relationships" in rel_result.data
        relationships = rel_result.data["relationships"]
        assert len(relationships) >= 1
        assert any(r["source_entity_id"] == entity1_id for r in relationships)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_relationships_filter_direction_e2e(docker_services, mcp_server_url):
    """Test filtering relationships by direction"""
    async with Client(mcp_server_url) as client:
        # Create entities
        entity1_result = await client.call_tool("create_entity", {
            "name": "Entity 1",
            "entity_type": "Organization",
            "tags": []
        })
        entity1_id = entity1_result.data.id

        entity2_result = await client.call_tool("create_entity", {
            "name": "Entity 2",
            "entity_type": "Individual",
            "tags": []
        })
        entity2_id = entity2_result.data.id

        # Create relationship
        await client.call_tool("create_entity_relationship", {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "relationship_type": "manages"
        })

        # Get outgoing relationships
        outgoing_result = await client.call_tool("get_entity_relationships", {
            "entity_id": entity1_id,
            "direction": "outgoing"
        })

        relationships = outgoing_result.data["relationships"]
        assert len(relationships) >= 1
        assert all(r["source_entity_id"] == entity1_id for r in relationships)

        # Get incoming relationships (should be 0)
        incoming_result = await client.call_tool("get_entity_relationships", {
            "entity_id": entity1_id,
            "direction": "incoming"
        })

        incoming_rels = incoming_result.data["relationships"]
        # Filter to only this test's relationships
        incoming_test_rels = [r for r in incoming_rels if r["target_entity_id"] == entity1_id and r["source_entity_id"] == entity2_id]
        assert len(incoming_test_rels) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test updating entity relationship"""
    async with Client(mcp_server_url) as client:
        # Create entities and relationship
        entity1_result = await client.call_tool("create_entity", {
            "name": "Entity A",
            "entity_type": "Organization",
            "tags": []
        })
        entity1_id = entity1_result.data.id

        entity2_result = await client.call_tool("create_entity", {
            "name": "Entity B",
            "entity_type": "Individual",
            "tags": []
        })
        entity2_id = entity2_result.data.id

        rel_result = await client.call_tool("create_entity_relationship", {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "relationship_type": "partners_with",
            "strength": 0.5
        })
        rel_id = rel_result.data.id

        # Update relationship
        update_result = await client.call_tool("update_entity_relationship", {
            "relationship_id": rel_id,
            "strength": 0.95,
            "confidence": 0.9,
            "metadata": {"updated": True}
        })

        assert update_result.data.strength == 0.95
        assert update_result.data.confidence == 0.9
        assert update_result.data.metadata == {"updated": True}
        assert update_result.data.relationship_type == "partners_with"  # Unchanged


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test deleting entity relationship"""
    async with Client(mcp_server_url) as client:
        # Create entities and relationship
        entity1_result = await client.call_tool("create_entity", {
            "name": "Entity X",
            "entity_type": "Organization",
            "tags": []
        })
        entity1_id = entity1_result.data.id

        entity2_result = await client.call_tool("create_entity", {
            "name": "Entity Y",
            "entity_type": "Individual",
            "tags": []
        })
        entity2_id = entity2_result.data.id

        rel_result = await client.call_tool("create_entity_relationship", {
            "source_entity_id": entity1_id,
            "target_entity_id": entity2_id,
            "relationship_type": "works_with"
        })
        rel_id = rel_result.data.id

        # Delete relationship
        delete_result = await client.call_tool("delete_entity_relationship", {
            "relationship_id": rel_id
        })

        assert delete_result.data is not None
        assert delete_result.data["deleted_id"] == rel_id

        # Verify relationship is gone
        rel_list = await client.call_tool("get_entity_relationships", {
            "entity_id": entity1_id
        })

        relationships = rel_list.data["relationships"]
        assert not any(r["id"] == rel_id for r in relationships)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_not_found_e2e(docker_services, mcp_server_url):
    """Test error handling for non-existent entity"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("get_entity", {
                "entity_id": 999999
            })
            assert False, "Expected error for non-existent entity"
        except Exception as e:
            assert "not found" in str(e).lower()
