"""
Activity service for event-driven architecture.

Handles activity event persistence and querying with lazy retention cleanup.
Subscribes to the event bus to persist all events to the activity log.
"""

import logging
from datetime import datetime
from uuid import UUID

from app.config.settings import settings
from app.models.activity_models import (
    ActivityEvent,
    ActivityListResponse,
    EntityType,
    ActionType,
    ActorType,
)
from app.protocols.activity_protocol import ActivityRepository

logger = logging.getLogger(__name__)


class ActivityService:
    """Service layer for activity tracking operations.

    Orchestrates:
    - Event persistence (via event bus subscription)
    - Activity querying with filtering and pagination
    - Lazy retention cleanup on API access

    The service subscribes to "*.*" on the event bus to persist all events.
    """

    def __init__(
        self,
        activity_repo: ActivityRepository,
    ):
        """Initialize activity service with repository.

        Args:
            activity_repo: Activity repository implementation (protocol-based)
        """
        self.activity_repo = activity_repo
        logger.info("Activity service initialised")

    async def handle_event(self, event: ActivityEvent) -> None:
        """
        Event handler for the event bus.

        This method is subscribed to "*.*" to persist all events.
        Called asynchronously by the event bus (fire-and-forget).

        Args:
            event: The activity event to persist
        """
        if event.user_id is None:
            logger.warning(
                f"Received event without user_id: {event.entity_type}.{event.action}"
            )
            return

        try:
            user_id = UUID(event.user_id)
            await self.activity_repo.save_event(user_id, event)
            logger.debug(
                f"Persisted activity event: {event.entity_type}.{event.action}",
                extra={
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "action": event.action,
                },
            )
        except Exception:
            logger.exception(
                f"Failed to persist activity event: {event.entity_type}.{event.action}"
            )

    async def get_activity(
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
    ) -> ActivityListResponse:
        """
        Query activity events with filtering and pagination.

        Performs lazy retention cleanup before querying if ACTIVITY_RETENTION_DAYS
        is configured.

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
            ActivityListResponse with paginated events
        """
        logger.info(
            "querying activity",
            extra={
                "user_id": str(user_id),
                "entity_type": entity_type,
                "action": action,
                "entity_id": entity_id,
                "actor": actor,
                "limit": limit,
                "offset": offset,
            },
        )

        # Lazy retention cleanup
        await self._cleanup_if_configured(user_id)

        # Query events
        events, total = await self.activity_repo.query_events(
            user_id=user_id,
            entity_type=entity_type,
            action=action,
            entity_id=entity_id,
            actor=actor,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "activity retrieved",
            extra={
                "count": len(events),
                "total": total,
                "user_id": str(user_id),
            },
        )

        return ActivityListResponse(
            events=events,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_entity_history(
        self,
        user_id: UUID,
        entity_type: EntityType,
        entity_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> ActivityListResponse:
        """
        Get activity history for a specific entity.

        Convenience method for querying all events for a single entity.

        Args:
            user_id: User ID for ownership filtering
            entity_type: Entity type (memory, project, etc.)
            entity_id: Entity ID
            limit: Maximum results to return (1-100)
            offset: Skip N results for pagination

        Returns:
            ActivityListResponse with entity's activity history
        """
        return await self.get_activity(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )

    async def count_activity(
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
        return await self.activity_repo.count_events(
            user_id=user_id,
            entity_type=entity_type,
            action=action,
        )

    async def _cleanup_if_configured(self, user_id: UUID) -> None:
        """
        Perform lazy retention cleanup if configured.

        Only runs if ACTIVITY_RETENTION_DAYS is set to a positive value.
        This is called on every query to ensure expired events are cleaned up.

        Args:
            user_id: User ID for ownership filtering
        """
        retention_days = settings.ACTIVITY_RETENTION_DAYS
        if retention_days is not None and retention_days > 0:
            try:
                deleted = await self.activity_repo.cleanup_expired(
                    user_id=user_id,
                    retention_days=retention_days,
                )
                if deleted > 0:
                    logger.info(
                        f"Lazy cleanup removed {deleted} expired activity events",
                        extra={"user_id": str(user_id), "retention_days": retention_days},
                    )
            except Exception:
                logger.exception("Failed to perform lazy activity cleanup")
