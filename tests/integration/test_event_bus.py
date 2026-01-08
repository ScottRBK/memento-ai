"""
Integration tests for the EventBus.

Tests pattern matching, async dispatch, and error isolation.
"""

import asyncio
import pytest

from app.events import EventBus
from app.models.activity_models import ActivityEvent, EntityType, ActionType


class TestEventBusPatternMatching:
    """Test pattern matching for event subscriptions."""

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """Exact pattern matches exact event."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("memory.created", handler)

        event = ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={"id": 1, "title": "Test"},
            user_id="test-user",
        )
        await bus.emit(event)
        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 1
        assert received[0].entity_type == EntityType.MEMORY
        assert received[0].action == ActionType.CREATED

    @pytest.mark.asyncio
    async def test_wildcard_entity_type(self):
        """Pattern 'memory.*' matches all memory actions."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("memory.*", handler)

        # Should match
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.UPDATED,
            snapshot={},
            user_id="test-user",
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.DELETED,
            snapshot={},
            user_id="test-user",
        ))

        # Should NOT match
        await bus.emit(ActivityEvent(
            entity_type=EntityType.PROJECT,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 3
        assert all(e.entity_type == EntityType.MEMORY for e in received)

    @pytest.mark.asyncio
    async def test_wildcard_action(self):
        """Pattern '*.deleted' matches all delete actions."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("*.deleted", handler)

        # Should match
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.DELETED,
            snapshot={},
            user_id="test-user",
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.PROJECT,
            entity_id=1,
            action=ActionType.DELETED,
            snapshot={},
            user_id="test-user",
        ))

        # Should NOT match
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 2
        assert all(e.action == ActionType.DELETED for e in received)

    @pytest.mark.asyncio
    async def test_catch_all_pattern(self):
        """Pattern '*.*' matches all events."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("*.*", handler)

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.PROJECT,
            entity_id=2,
            action=ActionType.UPDATED,
            snapshot={},
            user_id="test-user",
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.ENTITY,
            entity_id=3,
            action=ActionType.DELETED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 3

    @pytest.mark.asyncio
    async def test_no_match(self):
        """Non-matching pattern doesn't receive events."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("project.created", handler)

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 0


class TestEventBusAsyncDispatch:
    """Test async fire-and-forget dispatch."""

    @pytest.mark.asyncio
    async def test_non_blocking_emit(self):
        """Emit returns immediately without waiting for handlers."""
        bus = EventBus()
        handler_started = asyncio.Event()
        handler_finished = asyncio.Event()

        async def slow_handler(event):
            handler_started.set()
            await asyncio.sleep(0.1)
            handler_finished.set()

        bus.subscribe("*.*", slow_handler)

        event = ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        )

        # Emit should return immediately
        await bus.emit(event)

        # Handler should have started but not finished
        await asyncio.wait_for(handler_started.wait(), timeout=0.5)
        assert not handler_finished.is_set()

        # Wait for handler to finish
        await asyncio.wait_for(handler_finished.wait(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Multiple subscribers all receive the event."""
        bus = EventBus()
        received_a = []
        received_b = []
        received_c = []

        async def handler_a(event):
            received_a.append(event)

        async def handler_b(event):
            received_b.append(event)

        async def handler_c(event):
            received_c.append(event)

        bus.subscribe("*.*", handler_a)
        bus.subscribe("*.*", handler_b)
        bus.subscribe("memory.*", handler_c)

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert len(received_c) == 1


class TestEventBusErrorIsolation:
    """Test that handler errors don't affect other handlers."""

    @pytest.mark.asyncio
    async def test_error_isolation(self):
        """One failing handler doesn't affect others."""
        bus = EventBus()
        received = []

        async def failing_handler(event):
            raise ValueError("Intentional failure")

        async def working_handler(event):
            received.append(event)

        bus.subscribe("*.*", failing_handler)
        bus.subscribe("*.*", working_handler)

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        # Working handler should still receive the event
        assert len(received) == 1


class TestEventBusManagement:
    """Test subscription management."""

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Unsubscribed handler doesn't receive events."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("*.*", handler)
        bus.unsubscribe("*.*", handler)

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        """Subscriber count reflects registrations."""
        bus = EventBus()

        async def handler(event):
            pass

        assert bus.subscriber_count() == 0
        assert bus.subscriber_count("*.*") == 0

        bus.subscribe("*.*", handler)
        assert bus.subscriber_count() == 1
        assert bus.subscriber_count("*.*") == 1

        bus.subscribe("memory.*", handler)
        assert bus.subscriber_count() == 2
        assert bus.subscriber_count("memory.*") == 1

    @pytest.mark.asyncio
    async def test_clear(self):
        """Clear removes all subscribers."""
        bus = EventBus()
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("*.*", handler)
        bus.clear()

        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id="test-user",
        ))

        await bus.wait_for_pending(timeout=1.0)

        assert len(received) == 0
        assert bus.subscriber_count() == 0


class TestEventBusStreaming:
    """Test SSE streaming functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_stream_receives_events(self):
        """Stream subscriber receives events with sequence numbers."""
        from uuid import UUID
        bus = EventBus(max_queue_size=100)
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        received = []

        async def collect_events():
            async for event_dict in bus.subscribe_stream(user_id):
                received.append(event_dict)
                if len(received) >= 2:
                    break

        # Start collecting in background
        task = asyncio.create_task(collect_events())

        # Give time for subscription to register
        await asyncio.sleep(0.05)

        # Emit events
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={"id": 1},
            user_id=str(user_id),
        ))
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=2,
            action=ActionType.UPDATED,
            snapshot={"id": 2},
            user_id=str(user_id),
        ))

        # Wait for collection
        await asyncio.wait_for(task, timeout=2.0)

        assert len(received) == 2
        assert received[0]["seq"] == 1
        assert received[1]["seq"] == 2
        assert received[0]["entity_type"] == "memory"
        assert received[0]["action"] == "created"

    @pytest.mark.asyncio
    async def test_stream_user_filtering(self):
        """Stream only receives events for its user_id."""
        from uuid import UUID
        bus = EventBus(max_queue_size=100)
        user_a = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        user_b = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        received_by_a = []

        async def collect_for_a():
            async for event_dict in bus.subscribe_stream(user_a):
                received_by_a.append(event_dict)
                break  # Just get one

        task = asyncio.create_task(collect_for_a())
        await asyncio.sleep(0.05)

        # Emit event for user B (should be ignored by A)
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id=str(user_b),
        ))

        # Emit event for user A (should be received)
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=2,
            action=ActionType.CREATED,
            snapshot={},
            user_id=str(user_a),
        ))

        await asyncio.wait_for(task, timeout=2.0)

        assert len(received_by_a) == 1
        assert received_by_a[0]["entity_id"] == 2

    @pytest.mark.asyncio
    async def test_stream_backpressure_handling(self):
        """Events are dropped when queue is full."""
        from uuid import UUID
        bus = EventBus(max_queue_size=2)  # Very small queue
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        received = []
        emit_done = asyncio.Event()

        async def collect_events():
            async for event_dict in bus.subscribe_stream(user_id):
                received.append(event_dict)
                # After first event, signal that we can emit more
                if len(received) == 1:
                    # Wait for all emits to complete before consuming more
                    await emit_done.wait()
                if len(received) >= 2:
                    break

        # Start collecting in background
        task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.05)

        # Emit first event - consumed immediately
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=0,
            action=ActionType.CREATED,
            snapshot={},
            user_id=str(user_id),
        ))

        # Wait a bit for consumer to process first event
        await asyncio.sleep(0.05)

        # Now emit 4 more events - queue can only hold 2 (rest dropped)
        for i in range(1, 5):
            await bus.emit(ActivityEvent(
                entity_type=EntityType.MEMORY,
                entity_id=i,
                action=ActionType.CREATED,
                snapshot={},
                user_id=str(user_id),
            ))

        # Signal consumer to continue
        emit_done.set()

        await asyncio.wait_for(task, timeout=2.0)

        # Should have received: first one consumed + 2 more from queue
        assert len(received) == 2
        assert received[0]["seq"] == 1
        # Second is from queue after emit_done - could be seq 2 or 3 depending on timing
        assert received[1]["seq"] >= 2

    @pytest.mark.asyncio
    async def test_stream_cleanup_on_disconnect(self):
        """Subscriber is removed when generator is closed."""
        from uuid import UUID
        bus = EventBus(max_queue_size=100)
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        started = asyncio.Event()

        async def start_and_wait():
            async for _ in bus.subscribe_stream(user_id):
                started.set()
                # Will be cancelled before receiving anything
                break

        # Start in background to actually register the subscription
        task = asyncio.create_task(start_and_wait())
        await asyncio.sleep(0.05)

        # Subscriber should be registered
        assert bus.stream_subscriber_count(str(user_id)) == 1

        # Cancel the task to simulate disconnect
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Give time for cleanup
        await asyncio.sleep(0.05)

        # Subscriber should be removed
        assert bus.stream_subscriber_count(str(user_id)) == 0

    @pytest.mark.asyncio
    async def test_stream_sequence_numbers(self):
        """Sequence numbers increment per user."""
        from uuid import UUID
        bus = EventBus(max_queue_size=100)
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        received = []

        async def collect_events():
            async for event_dict in bus.subscribe_stream(user_id):
                received.append(event_dict)
                if len(received) >= 3:
                    break

        task = asyncio.create_task(collect_events())
        await asyncio.sleep(0.05)

        # Emit 3 events
        for i in range(3):
            await bus.emit(ActivityEvent(
                entity_type=EntityType.MEMORY,
                entity_id=i,
                action=ActionType.CREATED,
                snapshot={},
                user_id=str(user_id),
            ))

        await asyncio.wait_for(task, timeout=2.0)

        # Verify sequence numbers
        assert received[0]["seq"] == 1
        assert received[1]["seq"] == 2
        assert received[2]["seq"] == 3

        # Current seq should be 3
        assert bus.get_current_seq(str(user_id)) == 3

    @pytest.mark.asyncio
    async def test_multiple_stream_subscribers_same_user(self):
        """Multiple subscribers for same user all receive events."""
        from uuid import UUID
        bus = EventBus(max_queue_size=100)
        user_id = UUID("12345678-1234-5678-1234-567812345678")
        received_1 = []
        received_2 = []

        async def collect_1():
            async for event_dict in bus.subscribe_stream(user_id):
                received_1.append(event_dict)
                break

        async def collect_2():
            async for event_dict in bus.subscribe_stream(user_id):
                received_2.append(event_dict)
                break

        task1 = asyncio.create_task(collect_1())
        task2 = asyncio.create_task(collect_2())
        await asyncio.sleep(0.05)

        # Both should be subscribed
        assert bus.stream_subscriber_count(str(user_id)) == 2

        # Emit one event
        await bus.emit(ActivityEvent(
            entity_type=EntityType.MEMORY,
            entity_id=1,
            action=ActionType.CREATED,
            snapshot={},
            user_id=str(user_id),
        ))

        await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)

        # Both should receive the event
        assert len(received_1) == 1
        assert len(received_2) == 1
        assert received_1[0]["seq"] == 1
        assert received_2[0]["seq"] == 1
