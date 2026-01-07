"""
Activity tracking models for the event-driven architecture.

Supports tracking of all entity lifecycle events (created, updated, deleted)
and optionally read/query operations when ACTIVITY_TRACK_READS is enabled.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, List
from pydantic import BaseModel, Field, ConfigDict


class EntityType(str, Enum):
    """Types of entities that can generate activity events."""
    MEMORY = "memory"
    PROJECT = "project"
    DOCUMENT = "document"
    CODE_ARTIFACT = "code_artifact"
    ENTITY = "entity"
    LINK = "link"


class ActionType(str, Enum):
    """Types of actions that generate activity events."""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    READ = "read"      # Single entity fetch (opt-in via ACTIVITY_TRACK_READS)
    QUERIED = "queried"  # Search/query operation (opt-in via ACTIVITY_TRACK_READS)


class ActorType(str, Enum):
    """Types of actors that can trigger activity events."""
    USER = "user"
    SYSTEM = "system"
    LLM_MAINTENANCE = "llm-maintenance"


class ActivityEvent(BaseModel):
    """
    Event payload emitted when an entity changes.

    This is the in-memory event that flows through the event bus.
    Subscribers receive this and can persist, transform, or react to it.
    """
    entity_type: EntityType = Field(
        ...,
        description="Type of entity that changed"
    )
    entity_id: int = Field(
        0,
        description="ID of the entity (0 for links which use metadata for source/target)"
    )
    action: ActionType = Field(
        ...,
        description="What happened to the entity"
    )
    changes: dict[str, dict[str, Any]] | None = Field(
        None,
        description="For updates: {field: {old: value, new: value}}. Null for other actions."
    )
    snapshot: dict[str, Any] = Field(
        ...,
        description="Full entity state at event time (JSON serializable)"
    )
    actor: ActorType = Field(
        ActorType.USER,
        description="Who/what triggered this event"
    )
    actor_id: str | None = Field(
        None,
        max_length=255,
        description="Optional actor identifier (session ID, user ID, etc.)"
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Additional context (query params for searches, link details, etc.)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When this event occurred"
    )

    # User context - populated by event bus before dispatch
    user_id: str | None = Field(
        None,
        description="User ID for RLS context (set by event bus)"
    )

    model_config = ConfigDict(use_enum_values=True)


class ActivityLogEntry(BaseModel):
    """
    Persisted activity event with database ID.

    This is what gets stored in the activity_log table and
    returned from the activity API endpoint.
    """
    id: int = Field(..., description="Database ID")
    user_id: str = Field(..., description="User who owns this activity")
    entity_type: EntityType = Field(..., description="Type of entity that changed")
    entity_id: int = Field(..., description="ID of the entity")
    action: ActionType = Field(..., description="What happened")
    changes: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Field changes for updates"
    )
    snapshot: dict[str, Any] = Field(..., description="Entity state at event time")
    actor: ActorType = Field(..., description="Who triggered the event")
    actor_id: str | None = Field(None, description="Actor identifier")
    metadata: dict[str, Any] | None = Field(None, description="Extra context")
    created_at: datetime = Field(..., description="When event occurred")

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ActivityListResponse(BaseModel):
    """
    Paginated response for GET /api/v1/activity endpoint.
    """
    events: List[ActivityLogEntry] = Field(
        ...,
        description="Activity events matching query filters"
    )
    total: int = Field(
        ...,
        description="Total count of events matching filters (before pagination)"
    )
    limit: int = Field(
        ...,
        description="Maximum results per page"
    )
    offset: int = Field(
        ...,
        description="Number of results skipped"
    )

    model_config = ConfigDict(from_attributes=True)
