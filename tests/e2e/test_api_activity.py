"""
E2E tests for Activity REST API endpoints (PostgreSQL).

Uses in-process FastMCP server with real PostgreSQL to test the activity tracking system.
Tests the /api/v1/activity endpoints via ASGI transport (async http_client).
"""
import pytest
import asyncio
import json

pytestmark = pytest.mark.asyncio(loop_scope="session")


# Enable activity tracking + read/query event tracking for this test module
SETTINGS_OVERRIDE = {
    'ACTIVITY_ENABLED': True,
    'ACTIVITY_TRACK_READS': True,
}


@pytest.mark.e2e
class TestActivityAPIList:
    """Test GET /api/v1/activity endpoint."""

    async def test_list_activity_empty(self, http_client):
        """GET /api/v1/activity returns empty list initially."""
        response = await http_client.get("/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    async def test_list_activity_after_memory_created(self, http_client):
        """GET /api/v1/activity returns events after memory creation."""
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
        await asyncio.sleep(0.5)

        response = await http_client.get("/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 1
        assert data["total"] >= 1

        created_events = [e for e in data["events"] if e["action"] == "created"]
        assert len(created_events) >= 1

    async def test_list_activity_filter_by_entity_type(self, http_client):
        """GET /api/v1/activity filters by entity_type."""
        await http_client.post("/api/v1/memories", json={
            "title": "Memory for Entity Type Filter",
            "content": "Content for filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })

        await asyncio.sleep(0.5)

        response = await http_client.get("/api/v1/activity?entity_type=memory")
        assert response.status_code == 200
        data = response.json()

        for event in data["events"]:
            assert event["entity_type"] == "memory"

    async def test_list_activity_filter_by_action(self, http_client):
        """GET /api/v1/activity filters by action."""
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory for Action Filter",
            "content": "Content for action filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "Updated Title"}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get("/api/v1/activity?action=created")
        assert response.status_code == 200
        data = response.json()

        for event in data["events"]:
            assert event["action"] == "created"


@pytest.mark.e2e
class TestActivityAPIUpdates:
    """Test activity tracking for update operations."""

    async def test_update_generates_event_with_changes(self, http_client):
        """Memory update generates event with changes diff."""
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Original Title",
            "content": "Original content",
            "context": "Update test",
            "keywords": ["update"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "New Title", "importance": 9}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_id={memory_id}&action=updated"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        updated_event = data["events"][0]
        assert updated_event["action"] == "updated"
        assert updated_event["changes"] is not None

        changes = updated_event["changes"]
        assert "title" in changes
        assert changes["title"]["old"] == "Original Title"
        assert changes["title"]["new"] == "New Title"


@pytest.mark.e2e
class TestActivityAPIDelete:
    """Test activity tracking for delete operations."""

    async def test_delete_generates_event(self, http_client):
        """Memory deletion generates deleted event."""
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory to Delete",
            "content": "Content to delete",
            "context": "Delete test",
            "keywords": ["delete"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        await http_client.request(
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            json={"reason": "Test deletion"}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_id={memory_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        deleted_event = data["events"][0]
        assert deleted_event["action"] == "deleted"
        assert deleted_event["entity_type"] == "memory"


@pytest.mark.e2e
class TestActivityAPIReads:
    """Test activity tracking for read operations."""

    async def test_get_memory_generates_read_event(self, http_client):
        """GET /api/v1/memories/{id} generates read event when tracking enabled."""
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory for Read Test",
            "content": "Content for read event test",
            "context": "Read test",
            "keywords": ["read"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        await http_client.get(f"/api/v1/memories/{memory_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_id={memory_id}&action=read"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        read_event = data["events"][0]
        assert read_event["action"] == "read"
        assert read_event["entity_type"] == "memory"


@pytest.mark.e2e
class TestActivityAPIEntityHistory:
    """Test GET /api/v1/activity/{entity_type}/{entity_id} endpoint."""

    async def test_get_entity_history(self, http_client):
        """GET entity history returns all events for a specific entity."""
        create_response = await http_client.post("/api/v1/memories", json={
            "title": "Memory for History Test",
            "content": "Content for history test",
            "context": "History test",
            "keywords": ["history"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        await http_client.put(
            f"/api/v1/memories/{memory_id}",
            json={"title": "Updated Title", "importance": 8}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get(f"/api/v1/activity/memory/{memory_id}")
        assert response.status_code == 200
        data = response.json()

        actions = [e["action"] for e in data["events"]]
        assert "created" in actions
        assert "updated" in actions

    async def test_get_entity_history_invalid_type(self, http_client):
        """GET entity history returns 400 for invalid entity type."""
        response = await http_client.get("/api/v1/activity/invalid_type/1")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()


@pytest.mark.e2e
class TestActivityAPIValidation:
    """Test validation of activity API parameters."""

    async def test_invalid_limit_returns_400(self, http_client):
        """GET /api/v1/activity?limit=0 returns 400."""
        response = await http_client.get("/api/v1/activity?limit=0")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    async def test_limit_over_max_returns_400(self, http_client):
        """GET /api/v1/activity?limit=200 returns 400."""
        response = await http_client.get("/api/v1/activity?limit=200")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    async def test_invalid_offset_returns_400(self, http_client):
        """GET /api/v1/activity?offset=-1 returns 400."""
        response = await http_client.get("/api/v1/activity?offset=-1")
        assert response.status_code == 400
        assert "offset" in response.json()["error"].lower()

    async def test_invalid_action_returns_400(self, http_client):
        """GET /api/v1/activity?action=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?action=invalid")
        assert response.status_code == 400
        assert "action" in response.json()["error"].lower()

    async def test_invalid_entity_type_returns_400(self, http_client):
        """GET /api/v1/activity?entity_type=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?entity_type=invalid")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()

    async def test_invalid_actor_returns_400(self, http_client):
        """GET /api/v1/activity?actor=invalid returns 400."""
        response = await http_client.get("/api/v1/activity?actor=invalid")
        assert response.status_code == 400
        assert "actor" in response.json()["error"].lower()

    async def test_invalid_entity_id_returns_400(self, http_client):
        """GET /api/v1/activity?entity_id=abc returns 400."""
        response = await http_client.get("/api/v1/activity?entity_id=abc")
        assert response.status_code == 400
        assert "entity_id" in response.json()["error"].lower()


@pytest.mark.e2e
class TestActivityAPIStreamSSE:
    """Test GET /api/v1/activity/stream SSE endpoint."""

    async def test_stream_returns_sse_content_type(self, http_client):
        """GET /api/v1/activity/stream returns text/event-stream content type."""
        async with http_client.stream("GET", "/api/v1/activity/stream") as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

    async def test_stream_receives_created_event(self, http_client):
        """SSE stream receives memory.created event."""
        received_events = []

        async def stream_collector():
            try:
                async with http_client.stream(
                    "GET", "/api/v1/activity/stream", timeout=10.0
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
                            if len(received_events) >= 1:
                                return
            except Exception as e:
                print(f"Stream error: {e}")

        # Start stream as a concurrent task
        stream_task = asyncio.create_task(stream_collector())
        await asyncio.sleep(0.5)  # Let stream establish

        # Create a memory (should trigger event)
        create_response = await http_client.post(
            "/api/v1/memories",
            json={
                "title": "Memory for SSE Test",
                "content": "This should appear in the SSE stream.",
                "context": "SSE test",
                "keywords": ["sse", "stream"],
                "tags": ["test"],
                "importance": 7
            }
        )
        assert create_response.status_code == 201

        # Wait for event
        try:
            await asyncio.wait_for(stream_task, timeout=5.0)
        except asyncio.TimeoutError:
            stream_task.cancel()

        assert len(received_events) >= 1
        event = received_events[0]
        assert "seq" in event
        assert event["entity_type"] == "memory"
        assert event["action"] == "created"

    async def test_stream_filters_by_entity_type(self, http_client):
        """SSE stream respects entity_type query filter."""
        received_events = []

        async def stream_collector():
            try:
                async with http_client.stream(
                    "GET", "/api/v1/activity/stream?entity_type=project",
                    timeout=10.0
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
            except Exception as e:
                print(f"Stream error: {e}")

        # Start stream as a concurrent task
        stream_task = asyncio.create_task(stream_collector())
        await asyncio.sleep(0.5)

        # Create a memory (should NOT appear - filtered to project only)
        await http_client.post(
            "/api/v1/memories",
            json={
                "title": "Memory Should Be Filtered",
                "content": "This should not appear in project-filtered stream.",
                "context": "Filter test",
                "keywords": ["filter"],
                "tags": ["test"],
                "importance": 7
            }
        )

        # Give time for event to NOT arrive
        await asyncio.sleep(1.0)
        stream_task.cancel()
        try:
            await stream_task
        except asyncio.CancelledError:
            pass

        assert len(received_events) == 0

    async def test_stream_invalid_entity_type_returns_400(self, http_client):
        """SSE stream returns 400 for invalid entity_type filter."""
        response = await http_client.get("/api/v1/activity/stream?entity_type=invalid")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()

    async def test_stream_invalid_action_returns_400(self, http_client):
        """SSE stream returns 400 for invalid action filter."""
        response = await http_client.get("/api/v1/activity/stream?action=invalid")
        assert response.status_code == 400
        assert "action" in response.json()["error"].lower()

    async def test_stream_includes_sequence_numbers(self, http_client):
        """SSE events include monotonically increasing sequence numbers."""
        received_events = []

        async def stream_collector():
            try:
                async with http_client.stream(
                    "GET", "/api/v1/activity/stream", timeout=15.0
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
                            if len(received_events) >= 3:
                                return
            except Exception as e:
                print(f"Stream error: {e}")

        stream_task = asyncio.create_task(stream_collector())
        await asyncio.sleep(0.5)

        # Create 3 memories
        for i in range(3):
            await http_client.post(
                "/api/v1/memories",
                json={
                    "title": f"Sequence Test Memory {i}",
                    "content": f"Memory {i} for sequence number testing.",
                    "context": "Sequence test",
                    "keywords": ["sequence"],
                    "tags": ["test"],
                    "importance": 7
                }
            )
            await asyncio.sleep(0.1)

        try:
            await asyncio.wait_for(stream_task, timeout=10.0)
        except asyncio.TimeoutError:
            stream_task.cancel()

        assert len(received_events) >= 3
        for i in range(1, len(received_events)):
            assert received_events[i]["seq"] > received_events[i-1]["seq"]


# ============================================================================
# Project Activity Event Tests
# ============================================================================


@pytest.mark.e2e
class TestActivityAPIProject:
    """Test activity tracking for Project operations."""

    async def test_project_created_event(self, http_client):
        """POST /api/v1/projects generates created event."""
        create_response = await http_client.post(
            "/api/v1/projects",
            json={
                "name": "Test Project for Activity",
                "description": "Testing activity tracking for projects",
                "project_type": "development"
            }
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=project&entity_id={project_id}&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "project"
        assert event["action"] == "created"

    async def test_project_updated_event(self, http_client):
        """PUT /api/v1/projects/{id} generates updated event with changes."""
        create_response = await http_client.post(
            "/api/v1/projects",
            json={
                "name": "Original Project Name",
                "description": "Original description",
                "project_type": "development"
            }
        )
        project_id = create_response.json()["id"]

        await http_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Project Name"}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=project&entity_id={project_id}&action=updated"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["action"] == "updated"
        assert event["changes"] is not None
        assert "name" in event["changes"]

    async def test_project_deleted_event(self, http_client):
        """DELETE /api/v1/projects/{id} generates deleted event."""
        create_response = await http_client.post(
            "/api/v1/projects",
            json={
                "name": "Project to Delete",
                "description": "Will be deleted",
                "project_type": "development"
            }
        )
        project_id = create_response.json()["id"]

        await http_client.delete(f"/api/v1/projects/{project_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=project&entity_id={project_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "project"
        assert event["action"] == "deleted"


# ============================================================================
# Document Activity Event Tests
# ============================================================================


@pytest.mark.e2e
class TestActivityAPIDocument:
    """Test activity tracking for Document operations."""

    async def test_document_created_event(self, http_client):
        """POST /api/v1/documents generates created event."""
        create_response = await http_client.post(
            "/api/v1/documents",
            json={
                "title": "Test Document for Activity",
                "description": "Testing activity tracking",
                "content": "This is the document content for activity tracking test.",
                "document_type": "text",
                "tags": ["test", "activity"]
            }
        )
        assert create_response.status_code == 201
        doc_id = create_response.json()["id"]

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=document&entity_id={doc_id}&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "document"
        assert event["action"] == "created"

    async def test_document_deleted_event(self, http_client):
        """DELETE /api/v1/documents/{id} generates deleted event."""
        create_response = await http_client.post(
            "/api/v1/documents",
            json={
                "title": "Document to Delete",
                "description": "Will be deleted",
                "content": "Content for deletion test",
                "document_type": "text",
                "tags": ["test"]
            }
        )
        doc_id = create_response.json()["id"]

        await http_client.delete(f"/api/v1/documents/{doc_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=document&entity_id={doc_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "document"
        assert event["action"] == "deleted"


# ============================================================================
# Code Artifact Activity Event Tests
# ============================================================================


@pytest.mark.e2e
class TestActivityAPICodeArtifact:
    """Test activity tracking for Code Artifact operations."""

    async def test_code_artifact_created_event(self, http_client):
        """POST /api/v1/code-artifacts generates created event."""
        create_response = await http_client.post(
            "/api/v1/code-artifacts",
            json={
                "title": "Test Code Artifact",
                "description": "Testing activity tracking",
                "code": "def test(): pass",
                "language": "python",
                "tags": ["test", "activity"]
            }
        )
        assert create_response.status_code == 201
        artifact_id = create_response.json()["id"]

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=code_artifact&entity_id={artifact_id}&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "code_artifact"
        assert event["action"] == "created"

    async def test_code_artifact_deleted_event(self, http_client):
        """DELETE /api/v1/code-artifacts/{id} generates deleted event."""
        create_response = await http_client.post(
            "/api/v1/code-artifacts",
            json={
                "title": "Artifact to Delete",
                "description": "Will be deleted",
                "code": "print('hello')",
                "language": "python",
                "tags": ["test"]
            }
        )
        artifact_id = create_response.json()["id"]

        await http_client.delete(f"/api/v1/code-artifacts/{artifact_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=code_artifact&entity_id={artifact_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "code_artifact"
        assert event["action"] == "deleted"


# ============================================================================
# Entity Activity Event Tests
# ============================================================================


@pytest.mark.e2e
class TestActivityAPIEntity:
    """Test activity tracking for Entity operations."""

    async def test_entity_created_event(self, http_client):
        """POST /api/v1/entities generates created event."""
        create_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Test Entity for Activity",
                "entity_type": "Individual",
                "notes": "Testing activity tracking",
                "tags": ["test"]
            }
        )
        assert create_response.status_code == 201
        entity_id = create_response.json()["id"]

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=entity&entity_id={entity_id}&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "entity"
        assert event["action"] == "created"

    async def test_entity_deleted_event(self, http_client):
        """DELETE /api/v1/entities/{id} generates deleted event."""
        create_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Entity to Delete",
                "entity_type": "Individual",
                "tags": ["test"]
            }
        )
        entity_id = create_response.json()["id"]

        await http_client.delete(f"/api/v1/entities/{entity_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=entity&entity_id={entity_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "entity"
        assert event["action"] == "deleted"

    async def test_entity_memory_link_created_event(self, http_client):
        """POST /api/v1/entities/{id}/memories generates entity_memory_link created event."""
        memory_response = await http_client.post(
            "/api/v1/memories",
            json={
                "title": "Memory for Link Test",
                "content": "Content for entity-memory link test",
                "context": "Link test",
                "keywords": ["link"],
                "tags": ["test"],
                "importance": 7
            }
        )
        memory_id = memory_response.json()["id"]

        entity_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Entity for Link Test",
                "entity_type": "Individual",
                "tags": ["test"]
            }
        )
        entity_id = entity_response.json()["id"]

        await http_client.post(
            f"/api/v1/entities/{entity_id}/memories",
            json={"memory_id": memory_id}
        )

        await asyncio.sleep(0.5)

        response = await http_client.get(
            "/api/v1/activity?entity_type=entity_memory_link&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        link_events = [
            e for e in data["events"]
            if e["snapshot"].get("entity_id") == entity_id
            and e["snapshot"].get("memory_id") == memory_id
        ]
        assert len(link_events) >= 1
        event = link_events[0]
        assert event["entity_type"] == "entity_memory_link"
        assert event["action"] == "created"

    async def test_entity_relationship_created_event(self, http_client):
        """POST /api/v1/entities/{id}/relationships generates entity_relationship created event."""
        entity1_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Person for Relationship",
                "entity_type": "Individual",
                "tags": ["test"]
            }
        )
        entity1_id = entity1_response.json()["id"]

        entity2_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Company for Relationship",
                "entity_type": "Organization",
                "tags": ["test"]
            }
        )
        entity2_id = entity2_response.json()["id"]

        rel_response = await http_client.post(
            f"/api/v1/entities/{entity1_id}/relationships",
            json={
                "target_entity_id": entity2_id,
                "relationship_type": "works_for"
            }
        )
        assert rel_response.status_code == 201
        relationship_id = rel_response.json()["id"]

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=entity_relationship&entity_id={relationship_id}&action=created"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "entity_relationship"
        assert event["action"] == "created"

    async def test_entity_relationship_deleted_event(self, http_client):
        """DELETE /api/v1/entities/relationships/{id} generates deleted event."""
        entity1_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Person to Delete Relationship",
                "entity_type": "Individual",
                "tags": ["test"]
            }
        )
        entity1_id = entity1_response.json()["id"]

        entity2_response = await http_client.post(
            "/api/v1/entities",
            json={
                "name": "Company to Delete Relationship",
                "entity_type": "Organization",
                "tags": ["test"]
            }
        )
        entity2_id = entity2_response.json()["id"]

        rel_response = await http_client.post(
            f"/api/v1/entities/{entity1_id}/relationships",
            json={
                "target_entity_id": entity2_id,
                "relationship_type": "works_for"
            }
        )
        relationship_id = rel_response.json()["id"]

        await http_client.delete(f"/api/v1/entities/relationships/{relationship_id}")

        await asyncio.sleep(0.5)

        response = await http_client.get(
            f"/api/v1/activity?entity_type=entity_relationship&entity_id={relationship_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["entity_type"] == "entity_relationship"
        assert event["action"] == "deleted"
