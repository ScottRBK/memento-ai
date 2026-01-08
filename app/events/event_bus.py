"""
In-process async pub/sub event bus with pattern matching and SSE streaming.

The event bus provides:
- Pattern matching for subscriptions (e.g., "memory.*", "*.deleted", "*.*")
- Async fire-and-forget dispatch via asyncio.create_task()
- Error isolation per subscriber (one failing subscriber doesn't affect others)
- Queue-based streaming for SSE clients via subscribe_stream()

Events are emitted after successful database commits (async after commit pattern).
This ensures subscribers can't block the main operation and only see committed changes.
"""

import asyncio
import fnmatch
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any
from uuid import UUID

from app.models.activity_models import ActivityEvent

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[ActivityEvent], Awaitable[None]]


class EventBus:
    """
    In-process async pub/sub event bus with pattern matching and SSE streaming.

    Supports two subscription patterns:
    1. Handler-based (fire-and-forget): subscribe(pattern, handler)
    2. Queue-based (SSE streaming): subscribe_stream(user_id)

    Patterns use fnmatch-style matching:
    - "memory.*" matches memory.created, memory.updated, memory.deleted
    - "*.deleted" matches memory.deleted, project.deleted, entity.deleted
    - "*.*" matches all events (wildcard)

    Example usage:
        bus = EventBus()

        # Handler-based subscription
        async def log_handler(event: ActivityEvent):
            print(f"Event: {event.entity_type}.{event.action}")
        bus.subscribe("*.*", log_handler)

        # Queue-based SSE streaming
        async for event_dict in bus.subscribe_stream(user_id):
            yield {"event": "activity", "data": json.dumps(event_dict)}

        await bus.emit(ActivityEvent(entity_type="memory", action="created", ...))
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        """
        Initialize an empty event bus.

        Args:
            max_queue_size: Maximum events per SSE subscriber queue (backpressure).
                           When full, new events are dropped with a warning.
        """
        # Handler-based subscriptions (pattern -> handlers)
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._pending_tasks: set[asyncio.Task[None]] = set()

        # Queue-based SSE streaming (user_id -> queues)
        self._stream_subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._sequences: dict[str, int] = {}  # user_id -> next sequence number
        self._stream_lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

        logger.debug(
            "EventBus initialized",
            extra={"max_queue_size": max_queue_size}
        )

    def subscribe(self, pattern: str, handler: EventHandler) -> None:
        """
        Subscribe a handler to events matching the given pattern.

        Args:
            pattern: fnmatch-style pattern (e.g., "memory.*", "*.deleted", "*.*")
            handler: Async function that receives ActivityEvent

        Note:
            The same handler can be subscribed to multiple patterns.
            Handlers are called in the order they were subscribed.
        """
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)
        logger.debug(f"Subscribed handler to pattern: {pattern}")

    def unsubscribe(self, pattern: str, handler: EventHandler) -> bool:
        """
        Unsubscribe a handler from a pattern.

        Args:
            pattern: The pattern to unsubscribe from
            handler: The handler function to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        if pattern in self._subscribers:
            try:
                self._subscribers[pattern].remove(handler)
                logger.debug(f"Unsubscribed handler from pattern: {pattern}")
                return True
            except ValueError:
                pass
        return False

    async def emit(self, event: ActivityEvent) -> None:
        """
        Emit an event to all matching subscribers.

        Events are dispatched asynchronously using asyncio.create_task(),
        so this method returns immediately without waiting for handlers.
        Subscribers cannot block the emitting operation.

        Args:
            event: The activity event to emit

        Note:
            If no subscribers match, the event is silently dropped.
            Handler exceptions are logged but don't propagate.
        """
        event_name = f"{event.entity_type}.{event.action}"
        matching_handlers: list[EventHandler] = []

        # Find all handlers whose patterns match this event
        for pattern, handlers in self._subscribers.items():
            if fnmatch.fnmatch(event_name, pattern):
                matching_handlers.extend(handlers)

        if matching_handlers:
            logger.debug(
                f"Dispatching {event_name} to {len(matching_handlers)} handler(s)"
            )

            # Fire-and-forget dispatch to each handler
            for handler in matching_handlers:
                task = asyncio.create_task(self._safe_dispatch(handler, event))
                # Track task to prevent garbage collection
                self._pending_tasks.add(task)
                task.add_done_callback(self._pending_tasks.discard)
        else:
            logger.debug(f"No handler subscribers for event: {event_name}")

        # Also push to SSE stream subscribers for this user
        if event.user_id:
            await self._emit_to_streams(event)

    async def _safe_dispatch(
        self, handler: EventHandler, event: ActivityEvent
    ) -> None:
        """
        Dispatch event to handler with error isolation.

        Any exception from the handler is logged but not propagated,
        ensuring one failing handler doesn't affect others.

        Args:
            handler: The async handler function
            event: The event to dispatch
        """
        try:
            await handler(event)
        except Exception:
            event_name = f"{event.entity_type}.{event.action}"
            logger.exception(
                f"Event handler failed for {event_name}",
                extra={
                    "event_type": event.entity_type,
                    "event_action": event.action,
                    "entity_id": event.entity_id,
                },
            )

    async def wait_for_pending(self, timeout: float | None = None) -> None:
        """
        Wait for all pending event handlers to complete.

        This is primarily useful for testing to ensure all async
        handlers have finished before making assertions.

        Args:
            timeout: Maximum seconds to wait (None = wait forever)

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        if self._pending_tasks:
            await asyncio.wait_for(
                asyncio.gather(*self._pending_tasks, return_exceptions=True),
                timeout=timeout,
            )

    def subscriber_count(self, pattern: str | None = None) -> int:
        """
        Get the number of subscribers.

        Args:
            pattern: If provided, count only subscribers for this pattern.
                    If None, count all subscribers across all patterns.

        Returns:
            Number of subscribed handlers
        """
        if pattern is not None:
            return len(self._subscribers.get(pattern, []))
        return sum(len(handlers) for handlers in self._subscribers.values())

    def clear(self) -> None:
        """Remove all subscribers from the event bus."""
        self._subscribers.clear()
        self._stream_subscribers.clear()
        self._sequences.clear()
        logger.debug("EventBus cleared all subscribers")

    # =========================================================================
    # SSE Streaming Methods
    # =========================================================================

    async def subscribe_stream(
        self, user_id: UUID
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Subscribe to events for a user via async generator (for SSE streaming).

        Events are filtered to only those belonging to the specified user.
        Each event includes a sequence number for gap detection.

        Args:
            user_id: User ID to filter events for

        Yields:
            Event dictionaries with 'seq' field for gap detection

        Example:
            async for event_dict in event_bus.subscribe_stream(user_id):
                yield {"event": "activity", "data": json.dumps(event_dict)}
        """
        user_id_str = str(user_id)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self._max_queue_size
        )

        async with self._stream_lock:
            if user_id_str not in self._stream_subscribers:
                self._stream_subscribers[user_id_str] = set()
            self._stream_subscribers[user_id_str].add(queue)

        logger.info(
            "SSE subscriber connected",
            extra={"user_id": user_id_str, "subscriber_count": len(self._stream_subscribers[user_id_str])}
        )

        try:
            while True:
                event_dict = await queue.get()
                yield event_dict
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            async with self._stream_lock:
                if user_id_str in self._stream_subscribers:
                    self._stream_subscribers[user_id_str].discard(queue)
                    if not self._stream_subscribers[user_id_str]:
                        del self._stream_subscribers[user_id_str]
            logger.info(
                "SSE subscriber disconnected",
                extra={"user_id": user_id_str}
            )

    async def _emit_to_streams(self, event: ActivityEvent) -> None:
        """
        Push event to all stream subscribers for this user.

        Adds a sequence number for client gap detection.
        Drops events if queue is full (backpressure).

        Args:
            event: The activity event to push
        """
        if not event.user_id:
            return

        user_id_str = event.user_id
        seq = self._next_seq(user_id_str)

        # Create event dict with sequence number
        event_dict = {"seq": seq, **event.model_dump(mode="json")}

        async with self._stream_lock:
            queues = list(self._stream_subscribers.get(user_id_str, set()))

        if not queues:
            return

        dropped_count = 0
        for queue in queues:
            try:
                queue.put_nowait(event_dict)
            except asyncio.QueueFull:
                dropped_count += 1

        if dropped_count > 0:
            logger.warning(
                f"SSE queue full, dropped event for {dropped_count} subscriber(s)",
                extra={
                    "user_id": user_id_str,
                    "seq": seq,
                    "event_type": f"{event.entity_type}.{event.action}",
                    "dropped_count": dropped_count,
                }
            )

    def _next_seq(self, user_id: str) -> int:
        """
        Get the next sequence number for a user.

        Sequence numbers are monotonically increasing per user.
        They reset when the server restarts.

        Args:
            user_id: User ID string

        Returns:
            Next sequence number (starts at 1)
        """
        if user_id not in self._sequences:
            self._sequences[user_id] = 0
        self._sequences[user_id] += 1
        return self._sequences[user_id]

    def stream_subscriber_count(self, user_id: str | None = None) -> int:
        """
        Get the number of SSE stream subscribers.

        Args:
            user_id: If provided, count only subscribers for this user.
                    If None, count all stream subscribers.

        Returns:
            Number of active SSE stream subscribers
        """
        if user_id is not None:
            return len(self._stream_subscribers.get(user_id, set()))
        return sum(len(queues) for queues in self._stream_subscribers.values())

    def get_current_seq(self, user_id: str) -> int:
        """
        Get the current sequence number for a user (for debugging/monitoring).

        Args:
            user_id: User ID string

        Returns:
            Current sequence number (0 if no events emitted yet)
        """
        return self._sequences.get(user_id, 0)
