"""
Activity repository for PostgreSQL data access operations.

Handles persistence and querying of activity events for the
event-driven architecture (Issue #7).
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, select

from app.models.activity_models import (
    ActivityEvent,
    ActivityLogEntry,
    EntityType,
    ActionType,
    ActorType,
)
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.postgres_tables import ActivityLogTable

logger = logging.getLogger(__name__)


class PostgresActivityRepository:
    """
    Repository for Activity Log operations in PostgreSQL.

    Provides persistence and querying of activity events with
    support for filtering, pagination, and retention cleanup.
    """

    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        self.db_adapter = db_adapter

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
        async with self.db_adapter.session(user_id) as session:
            activity_orm = ActivityLogTable(
                user_id=user_id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                action=event.action,
                changes=event.changes,
                snapshot=event.snapshot,
                actor=event.actor,
                actor_id=event.actor_id,
                event_metadata=event.metadata,
                created_at=event.created_at,
            )
            session.add(activity_orm)
            await session.flush()
            await session.refresh(activity_orm)

            logger.debug(
                f"Saved activity event: {event.entity_type}.{event.action} "
                f"(id={activity_orm.id})"
            )

            return ActivityLogEntry(
                id=activity_orm.id,
                user_id=str(user_id),
                entity_type=activity_orm.entity_type,
                entity_id=activity_orm.entity_id,
                action=activity_orm.action,
                changes=activity_orm.changes,
                snapshot=activity_orm.snapshot,
                actor=activity_orm.actor,
                actor_id=activity_orm.actor_id,
                metadata=activity_orm.event_metadata,
                created_at=activity_orm.created_at,
            )

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
        async with self.db_adapter.session(user_id) as session:
            # Build base query with filters
            # RLS handles user_id filtering in PostgreSQL
            base_query = select(ActivityLogTable)

            if entity_type is not None:
                base_query = base_query.where(
                    ActivityLogTable.entity_type == entity_type
                )

            if action is not None:
                base_query = base_query.where(ActivityLogTable.action == action)

            if entity_id is not None:
                base_query = base_query.where(
                    ActivityLogTable.entity_id == entity_id
                )

            if actor is not None:
                base_query = base_query.where(ActivityLogTable.actor == actor)

            if since is not None:
                base_query = base_query.where(
                    ActivityLogTable.created_at >= since
                )

            if until is not None:
                base_query = base_query.where(
                    ActivityLogTable.created_at <= until
                )

            # Get total count (before pagination)
            count_query = select(func.count()).select_from(
                base_query.subquery()
            )
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0

            # Apply pagination and ordering
            paginated_query = (
                base_query.order_by(ActivityLogTable.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(paginated_query)
            activity_orms = result.scalars().all()

            events = [
                ActivityLogEntry(
                    id=activity.id,
                    user_id=str(activity.user_id),
                    entity_type=activity.entity_type,
                    entity_id=activity.entity_id,
                    action=activity.action,
                    changes=activity.changes,
                    snapshot=activity.snapshot,
                    actor=activity.actor,
                    actor_id=activity.actor_id,
                    metadata=activity.event_metadata,
                    created_at=activity.created_at,
                )
                for activity in activity_orms
            ]

            return events, total_count

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
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        async with self.db_adapter.session(user_id) as session:
            # Count events to be deleted (RLS handles user filtering)
            count_query = select(func.count()).select_from(ActivityLogTable).where(
                ActivityLogTable.created_at < cutoff_date,
            )
            count_result = await session.execute(count_query)
            count = count_result.scalar() or 0

            if count > 0:
                # Delete expired events (RLS handles user filtering)
                delete_stmt = delete(ActivityLogTable).where(
                    ActivityLogTable.created_at < cutoff_date,
                )
                await session.execute(delete_stmt)
                logger.info(
                    f"Cleaned up {count} expired activity events "
                    f"(older than {retention_days} days)"
                )

            return count

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
        async with self.db_adapter.session(user_id) as session:
            # RLS handles user filtering in PostgreSQL
            query = select(func.count()).select_from(ActivityLogTable)

            if entity_type is not None:
                query = query.where(ActivityLogTable.entity_type == entity_type)

            if action is not None:
                query = query.where(ActivityLogTable.action == action)

            result = await session.execute(query)
            return result.scalar() or 0
