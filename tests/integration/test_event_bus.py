"""
Integration tests for the EventBus.

Tests pattern matching, async dispatch, and error isolation.
"""

import asyncio
import pytest

from app.events import EventBus
from app.models.activity_models import ActivityEvent, EntityType, ActionType, ActorType


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
