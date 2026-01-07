"""
In-process async pub/sub event bus with pattern matching.

The event bus provides:
- Pattern matching for subscriptions (e.g., "memory.*", "*.deleted", "*.*")
- Async fire-and-forget dispatch via asyncio.create_task()
- Error isolation per subscriber (one failing subscriber doesn't affect others)

Events are emitted after successful database commits (async after commit pattern).
This ensures subscribers can't block the main operation and only see committed changes.
"""

import asyncio
import fnmatch
import logging
from collections.abc import Awaitable, Callable

from app.models.activity_models import ActivityEvent

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[ActivityEvent], Awaitable[None]]


class EventBus:
    """
    In-process async pub/sub event bus with pattern matching.

    Patterns use fnmatch-style matching:
    - "memory.*" matches memory.created, memory.updated, memory.deleted
    - "*.deleted" matches memory.deleted, project.deleted, entity.deleted
    - "*.*" matches all events (wildcard)

    Example usage:
        bus = EventBus()

        async def log_handler(event: ActivityEvent):
            print(f"Event: {event.entity_type}.{event.action}")

        bus.subscribe("*.*", log_handler)
        await bus.emit(ActivityEvent(entity_type="memory", action="created", ...))
    """

    def __init__(self) -> None:
        """Initialize an empty event bus."""
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._pending_tasks: set[asyncio.Task[None]] = set()
        logger.debug("EventBus initialized")

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

        if not matching_handlers:
            logger.debug(f"No subscribers for event: {event_name}")
            return

        logger.debug(
            f"Dispatching {event_name} to {len(matching_handlers)} handler(s)"
        )

        # Fire-and-forget dispatch to each handler
        for handler in matching_handlers:
            task = asyncio.create_task(self._safe_dispatch(handler, event))
            # Track task to prevent garbage collection
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

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
        logger.debug("EventBus cleared all subscribers")
