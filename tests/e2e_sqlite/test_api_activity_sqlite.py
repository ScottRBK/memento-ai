"""
E2E tests for Activity REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/activity endpoints.

NOTE: Event-driven activity tracking is disabled for SQLite E2E tests because
async event handling conflicts with SQLite's StaticPool (in-memory mode).
Tests that rely on automatic event emission are skipped here.
Full event-driven tests run in PostgreSQL E2E suite (tests/e2e/).
"""
import asyncio
import pytest

# Skip reason for event-dependent tests
SKIP_REASON = (
    "Activity event tracking disabled for SQLite tests due to async/StaticPool conflicts. "
    "See PostgreSQL E2E tests for full coverage."
)


@pytest.mark.skip(reason=SKIP_REASON)
class TestActivityAPIList:
    """Test GET /api/v1/activity endpoint."""

    @pytest.mark.asyncio
    async def test_list_activity_empty(self, http_client):
        """GET /api/v1/activity returns empty list initially."""
        response = await http_client.get("/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_activity_after_memory_created(self, http_client):
        """GET /api/v1/activity returns events after memory creation."""
        # Create a memory (should emit memory.created event)
        payload = {
            "title": "Test Memory for Activity",
            "content": "This is test content for activity tracking.",
            "context": "Testing activity API",
            "keywords": ["test", "activity"],
            "tags": ["test"],
            "importance": 7
        }
        create_response = await http_client.post("/api/v1/memories", json=payload)
        assert create_response.status_code == 201

        # Wait for async event processing
        await asyncio.sleep(0.1)

        # Now list activity
        response = await http_client.get("/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 1
        assert data["total"] >= 1

        # Verify the created event
        created_events = [e for e in data["events"] if e["action"] == "created"]
        assert len(created_events) >= 1

    @pytest.mark.asyncio
    async def test_list_activity_with_pagination(self, http_client):
        """GET /api/v1/activity respects limit and offset."""
        # Create 3 memories to generate events
        for i in range(3):
            payload = {
                "title": f"Pagination Memory {i}",
                "content": f"Content for pagination test {i}",
                "context": "Pagination test",
                "keywords": ["pagination"],
                "tags": ["test"],
                "importance": 7
            }
            await http_client.post("/api/v1/memories", json=payload)

        # Wait for async event processing
        await asyncio.sleep(0.1)

        # Get first page with limit=2
        response = await http_client.get("/api/v1/activity?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) <= 2
        assert data["limit"] == 2
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_activity_filter_by_entity_type(self, http_client):
        """GET /api/v1/activity filters by entity_type."""
        # Create a memory
        await http_client.post("/api/v1/memories", json={
            "title": "Memory for Entity Type Filter",
            "content": "Content for filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })

        await asyncio.sleep(0.1)

        # Filter by memory entity_type
        response = await http_client.get("/api/v1/activity?entity_type=memory")
        assert response.status_code == 200
        data = response.json()

        # All events should be memory events
        for event in data["events"]:
            assert event["entity_type"] == "memory"

    @pytest.mark.asyncio
    async def test_list_activity_filter_by_action(self, http_client):
        """GET /api/v1/activity filters by action."""
        # Create and update a memory
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory for Action Filter",
            "content": "Content for action filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "Updated Title"}
        )

        await asyncio.sleep(0.1)

        # Filter by created action
        response = await http_client.get("/api/v1/activity?action=created")
        assert response.status_code == 200
        data = response.json()

        # All events should be created actions
        for event in data["events"]:
            assert event["action"] == "created"

    @pytest.mark.asyncio
    async def test_list_activity_filter_by_entity_id(self, http_client):
        """GET /api/v1/activity filters by entity_id."""
        # Create two memories
        m1 = await http_client.post("/api/v1/memories", json={
            "title": "Memory 1 for Entity ID Filter",
            "content": "First memory content",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })
        m1_id = m1.json()["id"]

        await http_client.post("/api/v1/memories", json={
            "title": "Memory 2 for Entity ID Filter",
            "content": "Second memory content",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })

        await asyncio.sleep(0.1)

        # Filter by specific entity_id
        response = await http_client.get(f"/api/v1/activity?entity_id={m1_id}")
        assert response.status_code == 200
        data = response.json()

        # All events should be for memory 1
        for event in data["events"]:
            assert event["entity_id"] == m1_id


@pytest.mark.skip(reason=SKIP_REASON)
class TestActivityAPIUpdates:
    """Test activity tracking for update operations."""

    @pytest.mark.asyncio
    async def test_update_generates_event_with_changes(self, http_client):
        """Memory update generates event with changes diff."""
        # Create a memory
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Original Title",
            "content": "Original content",
            "context": "Update test",
            "keywords": ["update"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "New Title", "importance": 9}
        )

        await asyncio.sleep(0.1)

        # Get activity for this memory
        response = await http_client.get(f"/api/v1/activity?entity_id={memory_id}&action=updated")
        assert response.status_code == 200
        data = response.json()

        # Should have an updated event
        assert len(data["events"]) >= 1
        updated_event = data["events"][0]
        assert updated_event["action"] == "updated"
        assert updated_event["changes"] is not None

        # Changes should contain the diff
        changes = updated_event["changes"]
        assert "title" in changes
        assert changes["title"]["old"] == "Original Title"
        assert changes["title"]["new"] == "New Title"


@pytest.mark.skip(reason=SKIP_REASON)
class TestActivityAPIDelete:
    """Test activity tracking for delete operations."""

    @pytest.mark.asyncio
    async def test_delete_generates_event(self, http_client):
        """Memory deletion generates deleted event."""
        # Create a memory
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory to Delete",
            "content": "Content to delete",
            "context": "Delete test",
            "keywords": ["delete"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        # Delete the memory
        await http_client.request(
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            json={"reason": "Test deletion"}
        )

        await asyncio.sleep(0.1)

        # Get activity for this memory
        response = await http_client.get(f"/api/v1/activity?entity_id={memory_id}&action=deleted")
        assert response.status_code == 200
        data = response.json()

        # Should have a deleted event
        assert len(data["events"]) >= 1
        deleted_event = data["events"][0]
        assert deleted_event["action"] == "deleted"
        assert deleted_event["entity_type"] == "memory"


@pytest.mark.skip(reason=SKIP_REASON)
class TestActivityAPILinks:
    """Test activity tracking for link operations."""

    @pytest.mark.asyncio
    async def test_link_generates_event(self, http_client):
        """Memory linking generates link.created event."""
        # Create two memories with very different content to avoid auto-linking
        m1 = await http_client.post("/api/v1/memories", json={
            "title": "Astronomy Star Gazing",
            "content": "Observing celestial objects through telescopes.",
            "context": "Hobby related to space",
            "keywords": ["astronomy", "stars"],
            "tags": ["hobby"],
            "importance": 7
        })
        m2 = await http_client.post("/api/v1/memories", json={
            "title": "Baking Bread Recipe",
            "content": "Mix flour, water, yeast, and salt. Knead and bake.",
            "context": "Cooking techniques",
            "keywords": ["baking", "bread"],
            "tags": ["cooking"],
            "importance": 7
        })

        m1_id = m1.json()["id"]
        m2_id = m2.json()["id"]

        await asyncio.sleep(0.1)

        # Check current link event count
        response_before = await http_client.get("/api/v1/activity?entity_type=link&action=created")
        events_before = len(response_before.json()["events"])

        # Link them manually
        link_response = await http_client.post(
            f"/api/v1/memories/{m1_id}/links",
            json={"related_ids": [m2_id]}
        )

        await asyncio.sleep(0.1)

        # Get link events after
        response = await http_client.get("/api/v1/activity?entity_type=link&action=created")
        assert response.status_code == 200
        data = response.json()
        events_after = len(data["events"])

        # If the link was newly created (not already existing from auto-link),
        # we should have more events now
        # If already linked, no new event is expected (correct behavior)
        if link_response.json().get("linked", []):
            assert events_after > events_before

    @pytest.mark.asyncio
    async def test_unlink_generates_event(self, http_client):
        """Memory unlinking generates link.deleted event."""
        # Create and link two memories
        m1 = await http_client.post("/api/v1/memories", json={
            "title": "Mountain Hiking",
            "content": "Exploring trails in the mountains.",
            "context": "Outdoor adventure",
            "keywords": ["hiking"],
            "tags": ["outdoor"],
            "importance": 7
        })
        m2 = await http_client.post("/api/v1/memories", json={
            "title": "Pasta Recipe",
            "content": "Italian pasta carbonara.",
            "context": "Italian cooking",
            "keywords": ["pasta"],
            "tags": ["food"],
            "importance": 7
        })

        m1_id = m1.json()["id"]
        m2_id = m2.json()["id"]

        # Link them
        await http_client.post(
            f"/api/v1/memories/{m1_id}/links",
            json={"related_ids": [m2_id]}
        )

        # Unlink them
        await http_client.delete(f"/api/v1/memories/{m1_id}/links/{m2_id}")

        await asyncio.sleep(0.1)

        # Get link.deleted events
        response = await http_client.get("/api/v1/activity?entity_type=link&action=deleted")
        assert response.status_code == 200
        data = response.json()

        # Should have link.deleted events
        assert len(data["events"]) >= 1


class TestActivityAPIEntityHistory:
    """Test GET /api/v1/activity/{entity_type}/{entity_id} endpoint."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason=SKIP_REASON)
    async def test_get_entity_history(self, http_client):
        """GET entity history returns all events for a specific entity."""
        # Create a memory
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory for History Test",
            "content": "Content for history test",
            "context": "History test",
            "keywords": ["history"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "Updated Title", "importance": 8}
        )

        await asyncio.sleep(0.1)

        # Get entity history
        response = await http_client.get(f"/api/v1/activity/memory/{memory_id}")
        assert response.status_code == 200
        data = response.json()

        # Should have both created and updated events
        actions = [e["action"] for e in data["events"]]
        assert "created" in actions
        assert "updated" in actions

    @pytest.mark.asyncio
    async def test_get_entity_history_invalid_type(self, http_client):
        """GET entity history returns 400 for invalid entity type."""
        response = await http_client.get("/api/v1/activity/invalid_type/1")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()


class TestActivityAPIValidation:
    """Test validation of activity API parameters."""

    @pytest.mark.asyncio
    async def test_invalid_limit_returns_400(self, http_client):
        """GET /api/v1/activity?limit=0 returns 400."""
        response = await http_client.get("/api/v1/activity?limit=0")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_limit_over_max_returns_400(self, http_client):
        """GET /api/v1/activity?limit=200 returns 400."""
        response = await http_client.get("/api/v1/activity?limit=200")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_offset_returns_400(self, http_client):
        """GET /api/v1/activity?offset=-1 returns 400."""
        response = await http_client.get("/api/v1/activity?offset=-1")
        assert response.status_code == 400
        assert "offset" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_action_returns_400(self, http_client):
        """GET /api/v1/activity?action=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?action=invalid")
        assert response.status_code == 400
        assert "action" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_entity_type_returns_400(self, http_client):
        """GET /api/v1/activity?entity_type=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?entity_type=invalid")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_actor_returns_400(self, http_client):
        """GET /api/v1/activity?actor=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?actor=invalid")
        assert response.status_code == 400
        assert "actor" in response.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_entity_id_returns_400(self, http_client):
        """GET /api/v1/activity?entity_id=abc returns 400."""
        response = await http_client.get("/api/v1/activity?entity_id=abc")
        assert response.status_code == 400
        assert "entity_id" in response.json()["error"].lower()
