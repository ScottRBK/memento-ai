"""
Protocol definition for the Activity Repository.

Defines the contract for persisting and querying activity events
across different database backends (SQLite, PostgreSQL).
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.models.activity_models import (
    ActivityEvent,
    ActivityLogEntry,
    EntityType,
    ActionType,
    ActorType,
)


class ActivityRepository(Protocol):
    """Contract for the Activity Repository."""

    async def save_event(
        self,
        user_id: UUID,
        event: ActivityEvent,
    ) -> ActivityLogEntry:
        """
        Persist an activity event to the database.

        Args:
            user_id: User ID for ownership
            event: The activity event to persist

        Returns:
            The persisted activity log entry with database ID
        """
        ...

    async def query_events(
        self,
        user_id: UUID,
        entity_type: EntityType | None = None,
        action: ActionType | None = None,
        entity_id: int | None = None,
        actor: ActorType | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActivityLogEntry], int]:
        """
        Query activity events with filtering and pagination.

        Args:
            user_id: User ID for ownership filtering
            entity_type: Filter by entity type (memory, project, etc.)
            action: Filter by action (created, updated, deleted, read, queried)
            entity_id: Filter by specific entity ID
            actor: Filter by actor (user, system, llm-maintenance)
            since: Only events after this timestamp
            until: Only events before this timestamp
            limit: Maximum results to return (1-100)
            offset: Skip N results for pagination

        Returns:
            Tuple of (events, total_count) where total_count is
            the count BEFORE limit/offset applied (for pagination)
        """
        ...

    async def cleanup_expired(
        self,
        user_id: UUID,
        retention_days: int,
    ) -> int:
        """
        Delete activity events older than the retention period.

        Args:
            user_id: User ID for ownership filtering
            retention_days: Delete events older than this many days

        Returns:
            Number of events deleted
        """
        ...

    async def count_events(
        self,
        user_id: UUID,
        entity_type: EntityType | None = None,
        action: ActionType | None = None,
    ) -> int:
        """
        Count activity events matching filters.

        Args:
            user_id: User ID for ownership filtering
            entity_type: Filter by entity type (optional)
            action: Filter by action (optional)

        Returns:
            Total count of matching events
        """
        ...
