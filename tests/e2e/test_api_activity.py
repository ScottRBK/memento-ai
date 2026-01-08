"""
E2E tests for Activity REST API endpoints (PostgreSQL).

Uses Docker Compose with real PostgreSQL to test the activity tracking system.
Tests the /api/v1/activity endpoints in a production-like environment.

Note: Activity tracking is enabled by default for all E2E tests via conftest.py
"""
import pytest
import httpx
import json


@pytest.mark.e2e
class TestActivityAPIList:
    """Test GET /api/v1/activity endpoint."""

    def test_list_activity_empty(self, docker_services, server_base_url):
        """GET /api/v1/activity returns empty list initially."""
        response = httpx.get(f"{server_base_url}/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_activity_after_memory_created(self, docker_services, server_base_url):
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
        create_response = httpx.post(
            f"{server_base_url}/api/v1/memories",
            json=payload
        )
        assert create_response.status_code == 201

        # Wait for async event processing
        import time
        time.sleep(0.5)

        # Now list activity
        response = httpx.get(f"{server_base_url}/api/v1/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 1
        assert data["total"] >= 1

        # Verify the created event
        created_events = [e for e in data["events"] if e["action"] == "created"]
        assert len(created_events) >= 1

    def test_list_activity_filter_by_entity_type(self, docker_services, server_base_url):
        """GET /api/v1/activity filters by entity_type."""
        # Create a memory
        httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Memory for Entity Type Filter",
            "content": "Content for filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })

        import time
        time.sleep(0.5)

        # Filter by memory entity_type
        response = httpx.get(f"{server_base_url}/api/v1/activity?entity_type=memory")
        assert response.status_code == 200
        data = response.json()

        # All events should be memory events
        for event in data["events"]:
            assert event["entity_type"] == "memory"

    def test_list_activity_filter_by_action(self, docker_services, server_base_url):
        """GET /api/v1/activity filters by action."""
        # Create and update a memory
        create_response = httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Memory for Action Filter",
            "content": "Content for action filter test",
            "context": "Filter test",
            "keywords": ["filter"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        httpx.put(
            f"{server_base_url}/api/v1/memories/{memory_id}",
            json={"title": "Updated Title"}
        )

        import time
        time.sleep(0.5)

        # Filter by created action
        response = httpx.get(f"{server_base_url}/api/v1/activity?action=created")
        assert response.status_code == 200
        data = response.json()

        # All events should be created actions
        for event in data["events"]:
            assert event["action"] == "created"


@pytest.mark.e2e
class TestActivityAPIUpdates:
    """Test activity tracking for update operations."""

    def test_update_generates_event_with_changes(self, docker_services, server_base_url):
        """Memory update generates event with changes diff."""
        # Create a memory
        create_response = httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Original Title",
            "content": "Original content",
            "context": "Update test",
            "keywords": ["update"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        httpx.put(
            f"{server_base_url}/api/v1/memories/{memory_id}",
            json={"title": "New Title", "importance": 9}
        )

        import time
        time.sleep(0.5)

        # Get activity for this memory
        response = httpx.get(
            f"{server_base_url}/api/v1/activity?entity_id={memory_id}&action=updated"
        )
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


@pytest.mark.e2e
class TestActivityAPIDelete:
    """Test activity tracking for delete operations."""

    def test_delete_generates_event(self, docker_services, server_base_url):
        """Memory deletion generates deleted event."""
        # Create a memory
        create_response = httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Memory to Delete",
            "content": "Content to delete",
            "context": "Delete test",
            "keywords": ["delete"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        # Delete the memory
        httpx.request(
            "DELETE",
            f"{server_base_url}/api/v1/memories/{memory_id}",
            json={"reason": "Test deletion"}
        )

        import time
        time.sleep(0.5)

        # Get activity for this memory
        response = httpx.get(
            f"{server_base_url}/api/v1/activity?entity_id={memory_id}&action=deleted"
        )
        assert response.status_code == 200
        data = response.json()

        # Should have a deleted event
        assert len(data["events"]) >= 1
        deleted_event = data["events"][0]
        assert deleted_event["action"] == "deleted"
        assert deleted_event["entity_type"] == "memory"


@pytest.mark.e2e
class TestActivityAPIReads:
    """Test activity tracking for read operations."""

    def test_get_memory_generates_read_event(self, docker_services, server_base_url):
        """GET /api/v1/memories/{id} generates read event when tracking enabled."""
        # Create a memory
        create_response = httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Memory for Read Test",
            "content": "Content for read event test",
            "context": "Read test",
            "keywords": ["read"],
            "tags": ["test"],
            "importance": 7
        })
        memory_id = create_response.json()["id"]

        # Read the memory (triggers READ event)
        httpx.get(f"{server_base_url}/api/v1/memories/{memory_id}")

        import time
        time.sleep(0.5)

        # Check for read event
        response = httpx.get(
            f"{server_base_url}/api/v1/activity?entity_id={memory_id}&action=read"
        )
        assert response.status_code == 200
        data = response.json()

        # Should have a read event
        assert len(data["events"]) >= 1
        read_event = data["events"][0]
        assert read_event["action"] == "read"
        assert read_event["entity_type"] == "memory"


@pytest.mark.e2e
class TestActivityAPIEntityHistory:
    """Test GET /api/v1/activity/{entity_type}/{entity_id} endpoint."""

    def test_get_entity_history(self, docker_services, server_base_url):
        """GET entity history returns all events for a specific entity."""
        # Create a memory
        create_response = httpx.post(f"{server_base_url}/api/v1/memories", json={
            "title": "Memory for History Test",
            "content": "Content for history test",
            "context": "History test",
            "keywords": ["history"],
            "tags": ["test"],
            "importance": 5
        })
        memory_id = create_response.json()["id"]

        # Update the memory
        httpx.put(
            f"{server_base_url}/api/v1/memories/{memory_id}",
            json={"title": "Updated Title", "importance": 8}
        )

        import time
        time.sleep(0.5)

        # Get entity history
        response = httpx.get(f"{server_base_url}/api/v1/activity/memory/{memory_id}")
        assert response.status_code == 200
        data = response.json()

        # Should have both created and updated events
        actions = [e["action"] for e in data["events"]]
        assert "created" in actions
        assert "updated" in actions

    def test_get_entity_history_invalid_type(self, docker_services, server_base_url):
        """GET entity history returns 400 for invalid entity type."""
        response = httpx.get(f"{server_base_url}/api/v1/activity/invalid_type/1")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()


@pytest.mark.e2e
class TestActivityAPIValidation:
    """Test validation of activity API parameters."""

    def test_invalid_limit_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?limit=0 returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?limit=0")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    def test_limit_over_max_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?limit=200 returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?limit=200")
        assert response.status_code == 400
        assert "limit" in response.json()["error"].lower()

    def test_invalid_offset_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?offset=-1 returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?offset=-1")
        assert response.status_code == 400
        assert "offset" in response.json()["error"].lower()

    def test_invalid_action_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?action=invalid returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?action=invalid")
        assert response.status_code == 400
        assert "action" in response.json()["error"].lower()

    def test_invalid_entity_type_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?entity_type=invalid returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?entity_type=invalid")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()

    def test_invalid_actor_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?actor=invalid returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?actor=invalid")
        assert response.status_code == 400
        assert "actor" in response.json()["error"].lower()

    def test_invalid_entity_id_returns_400(self, docker_services, server_base_url):
        """GET /api/v1/activity?entity_id=abc returns 400."""
        response = httpx.get(f"{server_base_url}/api/v1/activity?entity_id=abc")
        assert response.status_code == 400
        assert "entity_id" in response.json()["error"].lower()


@pytest.mark.e2e
class TestActivityAPIStreamSSE:
    """Test GET /api/v1/activity/stream SSE endpoint."""

    def test_stream_returns_sse_content_type(self, docker_services, server_base_url):
        """GET /api/v1/activity/stream returns text/event-stream content type."""
        with httpx.stream("GET", f"{server_base_url}/api/v1/activity/stream", timeout=5.0) as response:
            assert response.status_code == 200
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

    def test_stream_receives_created_event(self, docker_services, server_base_url):
        """SSE stream receives memory.created event."""
        import threading
        import time

        received_events = []
        stream_started = threading.Event()
        stop_streaming = threading.Event()

        def stream_collector():
            try:
                with httpx.stream(
                    "GET",
                    f"{server_base_url}/api/v1/activity/stream",
                    timeout=10.0
                ) as response:
                    stream_started.set()
                    for line in response.iter_lines():
                        if stop_streaming.is_set():
                            break
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
                            if len(received_events) >= 1:
                                break
            except Exception as e:
                print(f"Stream error: {e}")

        # Start stream in background thread
        thread = threading.Thread(target=stream_collector)
        thread.start()

        # Wait for stream to start
        stream_started.wait(timeout=5.0)
        time.sleep(0.5)  # Extra time for subscription registration

        # Create a memory (should trigger event)
        create_response = httpx.post(
            f"{server_base_url}/api/v1/memories",
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

        # Wait for event and cleanup
        thread.join(timeout=5.0)
        stop_streaming.set()

        # Verify we received the event
        assert len(received_events) >= 1
        event = received_events[0]
        assert "seq" in event
        assert event["entity_type"] == "memory"
        assert event["action"] == "created"

    def test_stream_filters_by_entity_type(self, docker_services, server_base_url):
        """SSE stream respects entity_type query filter."""
        import threading
        import time

        received_events = []
        stream_started = threading.Event()
        stop_streaming = threading.Event()

        def stream_collector():
            try:
                with httpx.stream(
                    "GET",
                    f"{server_base_url}/api/v1/activity/stream?entity_type=project",
                    timeout=10.0
                ) as response:
                    stream_started.set()
                    for line in response.iter_lines():
                        if stop_streaming.is_set():
                            break
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
            except Exception as e:
                print(f"Stream error: {e}")

        # Start stream in background thread
        thread = threading.Thread(target=stream_collector)
        thread.start()

        # Wait for stream to start
        stream_started.wait(timeout=5.0)
        time.sleep(0.5)

        # Create a memory (should NOT appear - filtered to project only)
        httpx.post(
            f"{server_base_url}/api/v1/memories",
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
        time.sleep(1.0)
        stop_streaming.set()
        thread.join(timeout=2.0)

        # Should not have received any events (memory events filtered out)
        assert len(received_events) == 0

    def test_stream_invalid_entity_type_returns_400(self, docker_services, server_base_url):
        """SSE stream returns 400 for invalid entity_type filter."""
        response = httpx.get(f"{server_base_url}/api/v1/activity/stream?entity_type=invalid")
        assert response.status_code == 400
        assert "entity_type" in response.json()["error"].lower()

    def test_stream_invalid_action_returns_400(self, docker_services, server_base_url):
        """SSE stream returns 400 for invalid action filter."""
        response = httpx.get(f"{server_base_url}/api/v1/activity/stream?action=invalid")
        assert response.status_code == 400
        assert "action" in response.json()["error"].lower()

    def test_stream_includes_sequence_numbers(self, docker_services, server_base_url):
        """SSE events include monotonically increasing sequence numbers."""
        import threading
        import time

        received_events = []
        stream_started = threading.Event()

        def stream_collector():
            try:
                with httpx.stream(
                    "GET",
                    f"{server_base_url}/api/v1/activity/stream",
                    timeout=15.0
                ) as response:
                    stream_started.set()
                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
                            if len(received_events) >= 3:
                                break
            except Exception as e:
                print(f"Stream error: {e}")

        # Start stream in background thread
        thread = threading.Thread(target=stream_collector)
        thread.start()

        # Wait for stream to start
        stream_started.wait(timeout=5.0)
        time.sleep(0.5)

        # Create 3 memories
        for i in range(3):
            httpx.post(
                f"{server_base_url}/api/v1/memories",
                json={
                    "title": f"Sequence Test Memory {i}",
                    "content": f"Memory {i} for sequence number testing.",
                    "context": "Sequence test",
                    "keywords": ["sequence"],
                    "tags": ["test"],
                    "importance": 7
                }
            )
            time.sleep(0.1)

        # Wait for events
        thread.join(timeout=10.0)

        # Verify sequence numbers are monotonically increasing
        assert len(received_events) >= 3
        for i in range(1, len(received_events)):
            assert received_events[i]["seq"] > received_events[i-1]["seq"]
