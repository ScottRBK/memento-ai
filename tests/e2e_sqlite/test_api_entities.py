"""
E2E tests for Entity REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/entities endpoints.
"""
import pytest


class TestEntityAPIList:
    """Test GET /api/v1/entities endpoint."""

    @pytest.mark.asyncio
    async def test_list_entities_empty(self, http_client):
        """GET /api/v1/entities returns empty list initially."""
        response = await http_client.get("/api/v1/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["entities"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_entities_with_data(self, http_client):
        """GET /api/v1/entities returns created entities."""
        # Create an entity first
        payload = {
            "name": "Test Person",
            "entity_type": "Individual",
            "notes": "A test individual"
        }
        create_response = await http_client.post("/api/v1/entities", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/entities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["entities"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_type(self, http_client):
        """GET /api/v1/entities filters by entity_type."""
        # Create entities of different types
        await http_client.post("/api/v1/entities", json={
            "name": "Test Organization",
            "entity_type": "Organization",
            "notes": "A test org"
        })
        await http_client.post("/api/v1/entities", json={
            "name": "Test Individual",
            "entity_type": "Individual",
            "notes": "A test person"
        })

        # Filter by organization
        response = await http_client.get("/api/v1/entities?entity_type=Organization")
        assert response.status_code == 200
        data = response.json()
        for entity in data["entities"]:
            assert entity["entity_type"] == "Organization"

    @pytest.mark.asyncio
    async def test_list_entities_invalid_entity_type(self, http_client):
        """GET /api/v1/entities returns 400 for invalid entity_type."""
        response = await http_client.get("/api/v1/entities?entity_type=invalid_type")
        assert response.status_code == 400
        assert "Invalid entity_type" in response.json()["error"]


class TestEntityAPICrud:
    """Test Entity CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_entity(self, http_client):
        """POST /api/v1/entities creates a new entity."""
        payload = {
            "name": "New Entity",
            "entity_type": "Team",
            "notes": "A new team entity"
        }
        response = await http_client.post("/api/v1/entities", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["name"] == "New Entity"
        assert data["entity_type"] == "Team"

    @pytest.mark.asyncio
    async def test_create_entity_validation_error(self, http_client):
        """POST /api/v1/entities returns 400 for invalid data."""
        payload = {
            "name": "",  # Empty name should fail
            "entity_type": "Individual"
        }
        response = await http_client.post("/api/v1/entities", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_entity(self, http_client):
        """GET /api/v1/entities/{id} returns the entity."""
        # Create first
        create_response = await http_client.post("/api/v1/entities", json={
            "name": "Get Test Entity",
            "entity_type": "Device",
            "notes": "Testing get endpoint"
        })
        entity_id = create_response.json()["id"]

        # Get
        response = await http_client.get(f"/api/v1/entities/{entity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == entity_id
        assert data["name"] == "Get Test Entity"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, http_client):
        """GET /api/v1/entities/{id} returns 404 for missing entity."""
        response = await http_client.get("/api/v1/entities/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_entity(self, http_client):
        """PUT /api/v1/entities/{id} updates the entity."""
        # Create first
        create_response = await http_client.post("/api/v1/entities", json={
            "name": "Update Test Entity",
            "entity_type": "Device",
            "notes": "Original notes"
        })
        entity_id = create_response.json()["id"]

        # Update
        update_payload = {
            "name": "Updated Entity Name",
            "notes": "Updated notes"
        }
        response = await http_client.put(f"/api/v1/entities/{entity_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Entity Name"
        assert data["notes"] == "Updated notes"

    @pytest.mark.asyncio
    async def test_update_entity_not_found(self, http_client):
        """PUT /api/v1/entities/{id} returns 404 for missing entity."""
        response = await http_client.put("/api/v1/entities/99999", json={"name": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_entity(self, http_client):
        """DELETE /api/v1/entities/{id} deletes the entity."""
        # Create first
        create_response = await http_client.post("/api/v1/entities", json={
            "name": "Delete Test Entity",
            "entity_type": "Other",
            "custom_type": "Temporary",
            "notes": "Will be deleted"
        })
        entity_id = create_response.json()["id"]

        # Delete
        response = await http_client.delete(f"/api/v1/entities/{entity_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/entities/{entity_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self, http_client):
        """DELETE /api/v1/entities/{id} returns 404 for missing entity."""
        response = await http_client.delete("/api/v1/entities/99999")
        assert response.status_code == 404


class TestEntityAPISearch:
    """Test entity search endpoint."""

    @pytest.mark.asyncio
    async def test_search_entities(self, http_client):
        """POST /api/v1/entities/search searches entities."""
        # Create some entities
        await http_client.post("/api/v1/entities", json={
            "name": "Searchable Company",
            "entity_type": "Organization",
            "notes": "A searchable organization"
        })

        # Search
        response = await http_client.post("/api/v1/entities/search", json={
            "query": "Searchable",
            "limit": 10
        })
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_search_entities_missing_query(self, http_client):
        """POST /api/v1/entities/search returns 400 without query."""
        response = await http_client.post("/api/v1/entities/search", json={})
        assert response.status_code == 400


class TestEntityMemoryLinks:
    """Test entity-memory link endpoints."""

    @pytest.mark.asyncio
    async def test_link_entity_to_memory(self, http_client):
        """POST /api/v1/entities/{id}/memories links entity to memory."""
        # Create entity
        entity_response = await http_client.post("/api/v1/entities", json={
            "name": "Link Test Entity",
            "entity_type": "Individual",
            "notes": "For link testing"
        })
        entity_id = entity_response.json()["id"]

        # Create memory
        memory_response = await http_client.post("/api/v1/memories", json={
            "title": "Link Test Memory",
            "content": "Memory for entity link testing",
            "context": "Testing entity links",
            "keywords": ["entity", "link"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = memory_response.json()["id"]

        # Link
        response = await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
            "memory_id": memory_id
        })
        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_link_entity_to_memory_missing_memory_id(self, http_client):
        """POST /api/v1/entities/{id}/memories returns 400 without memory_id."""
        # Create entity
        entity_response = await http_client.post("/api/v1/entities", json={
            "name": "Link Error Test Entity",
            "entity_type": "Individual",
            "notes": "For error testing"
        })
        entity_id = entity_response.json()["id"]

        response = await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unlink_entity_from_memory(self, http_client):
        """DELETE /api/v1/entities/{id}/memories/{memory_id} unlinks entity from memory."""
        # Create entity
        entity_response = await http_client.post("/api/v1/entities", json={
            "name": "Unlink Test Entity",
            "entity_type": "Organization",
            "notes": "For unlink testing"
        })
        entity_id = entity_response.json()["id"]

        # Create memory
        memory_response = await http_client.post("/api/v1/memories", json={
            "title": "Unlink Test Memory",
            "content": "Memory for entity unlink testing",
            "context": "Testing entity unlinks",
            "keywords": ["unlink", "test"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = memory_response.json()["id"]

        # Link first
        await http_client.post(f"/api/v1/entities/{entity_id}/memories", json={
            "memory_id": memory_id
        })

        # Unlink
        response = await http_client.delete(f"/api/v1/entities/{entity_id}/memories/{memory_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestEntityRelationships:
    """Test entity relationship endpoints."""

    @pytest.mark.asyncio
    async def test_create_entity_relationship(self, http_client):
        """POST /api/v1/entities/{id}/relationships creates a relationship."""
        # Create two entities
        entity1_response = await http_client.post("/api/v1/entities", json={
            "name": "Parent Entity",
            "entity_type": "Organization",
            "notes": "Parent org"
        })
        entity1_id = entity1_response.json()["id"]

        entity2_response = await http_client.post("/api/v1/entities", json={
            "name": "Child Entity",
            "entity_type": "Team",
            "notes": "Child team"
        })
        entity2_id = entity2_response.json()["id"]

        # Create relationship
        response = await http_client.post(f"/api/v1/entities/{entity1_id}/relationships", json={
            "target_entity_id": entity2_id,
            "relationship_type": "manages",
            "description": "Parent manages child"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["source_entity_id"] == entity1_id
        assert data["target_entity_id"] == entity2_id

    @pytest.mark.asyncio
    async def test_get_entity_relationships(self, http_client):
        """GET /api/v1/entities/{id}/relationships returns relationships."""
        # Create entity with relationship
        entity1_response = await http_client.post("/api/v1/entities", json={
            "name": "Relationship Source",
            "entity_type": "Individual",
            "notes": "Source entity"
        })
        entity1_id = entity1_response.json()["id"]

        entity2_response = await http_client.post("/api/v1/entities", json={
            "name": "Relationship Target",
            "entity_type": "Organization",
            "notes": "Target entity"
        })
        entity2_id = entity2_response.json()["id"]

        # Create relationship
        await http_client.post(f"/api/v1/entities/{entity1_id}/relationships", json={
            "target_entity_id": entity2_id,
            "relationship_type": "works_for",
            "description": "Employment"
        })

        # Get relationships
        response = await http_client.get(f"/api/v1/entities/{entity1_id}/relationships")
        assert response.status_code == 200
        data = response.json()
        assert "relationships" in data
        assert len(data["relationships"]) >= 1

    @pytest.mark.asyncio
    async def test_delete_entity_relationship(self, http_client):
        """DELETE /api/v1/entities/relationships/{id} deletes a relationship."""
        # Create entities
        entity1_response = await http_client.post("/api/v1/entities", json={
            "name": "Delete Rel Source",
            "entity_type": "Team",
            "notes": "Source"
        })
        entity1_id = entity1_response.json()["id"]

        entity2_response = await http_client.post("/api/v1/entities", json={
            "name": "Delete Rel Target",
            "entity_type": "Device",
            "notes": "Target"
        })
        entity2_id = entity2_response.json()["id"]

        # Create relationship
        rel_response = await http_client.post(f"/api/v1/entities/{entity1_id}/relationships", json={
            "target_entity_id": entity2_id,
            "relationship_type": "uses",
            "description": "Team uses device"
        })
        relationship_id = rel_response.json()["id"]

        # Delete relationship
        response = await http_client.delete(f"/api/v1/entities/relationships/{relationship_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True
