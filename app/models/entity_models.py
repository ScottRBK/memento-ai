"""
Pydantic models for Entity and EntityRelationship entities

Entities represent real-world entities (organizations, individuals, teams, devices)
that can be linked to memories and related to each other through a knowledge graph.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator

from app.config.settings import settings


class EntityType(str, Enum):
    """Predefined entity types"""
    ORGANIZATION = "Organization"
    INDIVIDUAL = "Individual"
    TEAM = "Team"
    DEVICE = "Device"
    OTHER = "Other"


class EntityCreate(BaseModel):
    """Request model for creating an entity

    Entities represent real-world entities like people, organizations, teams, and devices
    that can be linked to memories and related to each other through relationships.

    Examples:
        Person: name="Sarah Chen", entity_type="Individual", notes="Lead backend developer..."
        Company: name="TechFlow Systems", entity_type="Organization", notes="Cloud infrastructure provider..."
        Device: name="Cache Server 01", entity_type="Device", notes="Redis cluster primary node..."
        Custom: name="Message Queue", entity_type="Other", custom_type="Middleware"
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=settings.ENTITY_NAME_MAX_LENGTH,
        description="Entity name - searchable identifier (e.g., 'John Smith', 'Anthropic', 'Production DB')"
    )
    entity_type: EntityType = Field(
        ...,
        description="Entity type: Organization, Individual, Team, Device, or Other"
    )
    custom_type: str | None = Field(
        default=None,
        max_length=settings.ENTITY_TYPE_MAX_LENGTH,
        description="Custom entity type (required if entity_type is 'Other', e.g., 'Infrastructure', 'Tool', 'Location')"
    )
    notes: str | None = Field(
        default=None,
        max_length=settings.ENTITY_NOTES_MAX_LENGTH,
        description="Additional context and information about this entity (bio, description, purpose, etc.)"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=settings.ENTITY_TAGS_MAX_COUNT,
        description="Tags for categorization and discovery (e.g., ['engineering', 'leadership'], ['ai', 'startup'])"
    )
    project_id: int | None = Field(
        default=None,
        description="Optional project ID for immediate association with a project"
    )

    @field_validator("name", "custom_type", "notes")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # Ensure name is not empty after stripping
        if info.field_name == "name" and not stripped:
            raise ValueError("name cannot be empty or whitespace only")

        return stripped if stripped else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if not v:
            return []

        # Strip whitespace and remove empty strings
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.ENTITY_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.ENTITY_TAGS_MAX_COUNT} tags allowed")

        return cleaned

    @model_validator(mode='after')
    def validate_custom_type(self):
        """Ensure custom_type is provided when entity_type is Other"""
        if self.entity_type == EntityType.OTHER and not self.custom_type:
            raise ValueError("custom_type is required when entity_type is 'Other'")

        # Clear custom_type if entity_type is not Other
        if self.entity_type != EntityType.OTHER:
            self.custom_type = None

        return self


class EntityUpdate(BaseModel):
    """Request model for updating an entity

    Follows PATCH semantics: only provided fields are updated.
    None/omitted values mean "don't change this field".

    Examples:
        Update notes: EntityUpdate(notes="Updated information...")
        Add tags: EntityUpdate(tags=["tag1", "tag2"])
        Change type: EntityUpdate(entity_type="Organization")
    """
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.ENTITY_NAME_MAX_LENGTH,
        description="New name. Unchanged if null."
    )
    entity_type: EntityType | None = Field(
        default=None,
        description="New entity type. Unchanged if null."
    )
    custom_type: str | None = Field(
        default=None,
        max_length=settings.ENTITY_TYPE_MAX_LENGTH,
        description="New custom type (required if changing entity_type to 'Other'). Unchanged if null."
    )
    notes: str | None = Field(
        default=None,
        max_length=settings.ENTITY_NOTES_MAX_LENGTH,
        description="New notes. Unchanged if null. Empty string clears."
    )
    tags: List[str] | None = Field(
        default=None,
        max_length=settings.ENTITY_TAGS_MAX_COUNT,
        description="New tags (replaces existing). Unchanged if null. Empty list [] clears tags."
    )
    project_id: int | None = Field(
        default=None,
        description="New project association. Unchanged if null."
    )

    @field_validator("name", "custom_type", "notes")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # Don't allow empty after stripping for name (if provided)
        if info.field_name == "name" and not stripped:
            raise ValueError("name cannot be empty or whitespace only")

        # For optional fields, empty string means "clear field"
        return stripped if stripped else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if v is None:
            return None

        # Empty list is valid (clears tags)
        if not v:
            return []

        # Strip whitespace and remove empty strings
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.ENTITY_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.ENTITY_TAGS_MAX_COUNT} tags allowed")

        return cleaned

    @model_validator(mode='after')
    def validate_custom_type(self):
        """Ensure custom_type is provided when entity_type is Other"""
        if self.entity_type == EntityType.OTHER and not self.custom_type:
            raise ValueError("custom_type is required when entity_type is 'Other'")

        return self


class Entity(EntityCreate):
    """Complete entity model with generated fields

    Extends EntityCreate with system-generated fields (id, timestamps).
    Used for responses that include full entity details.

    Returned by:
    - create_entity: After successfully creating an entity
    - get_entity: When retrieving a specific entity by ID
    - update_entity: After successfully updating an entity
    """
    id: int = Field(
        ...,
        description="Unique entity identifier (auto-generated)"
    )
    project_id: int | None = Field(
        default=None,
        description="Associated project ID. Null if not linked to a project."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the entity was created (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the entity was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)


class EntitySummary(BaseModel):
    """Lightweight entity summary for list operations

    Excludes notes field to minimize token usage when listing
    multiple entities. Contains just enough info to identify and filter.

    Used by:
    - list_entities: When listing all entities or filtering by type/project/tags
    """
    id: int = Field(
        ...,
        description="Unique entity identifier"
    )
    name: str = Field(
        ...,
        description="Entity name"
    )
    entity_type: EntityType = Field(
        ...,
        description="Entity type"
    )
    custom_type: str | None = Field(
        default=None,
        description="Custom entity type (if entity_type is 'Other')"
    )
    tags: List[str] = Field(
        ...,
        description="Tags for categorization"
    )
    project_id: int | None = Field(
        default=None,
        description="Associated project ID"
    )
    created_at: datetime = Field(
        ...,
        description="When the entity was created (UTC)"
    )
    updated_at: datetime = Field(
        ...,
        description="When the entity was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)


# Entity Relationship Models

class EntityRelationshipCreate(BaseModel):
    """Request model for creating an entity relationship

    Relationships form a knowledge graph connecting entities with typed,
    weighted edges that can include confidence scores and metadata.

    Examples:
        Employment: source_entity_id=5, target_entity_id=12, relationship_type="works_at",
                    strength=0.9, confidence=0.95, metadata={"role": "Senior Engineer"}
        Ownership: source_entity_id=7, target_entity_id=3, relationship_type="owns",
                   strength=1.0, confidence=1.0, metadata={"since": "2023-01-01"}
    """
    source_entity_id: int = Field(
        ...,
        description="Source entity ID (the 'from' entity in the relationship)"
    )
    target_entity_id: int = Field(
        ...,
        description="Target entity ID (the 'to' entity in the relationship)"
    )
    relationship_type: str = Field(
        ...,
        min_length=1,
        max_length=settings.ENTITY_RELATIONSHIP_TYPE_MAX_LENGTH,
        description="Relationship type (e.g., 'works_at', 'owns', 'manages', 'part_of', 'reports_to')"
    )
    strength: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Relationship strength (0.0-1.0), indicating the significance or weight of this relationship"
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0), indicating certainty about this relationship"
    )
    metadata: Dict[str, Any] | None = Field(
        default=None,
        description="Flexible metadata dictionary for additional context (e.g., {'source': 'linkedin', 'last_verified': '2025-03-21'})"
    )

    @field_validator("relationship_type")
    @classmethod
    def strip_whitespace(cls, v):
        """Strip whitespace from relationship_type"""
        if v is None:
            return v

        stripped = v.strip()
        if not stripped:
            raise ValueError("relationship_type cannot be empty or whitespace only")

        return stripped

    @model_validator(mode='after')
    def validate_different_entities(self):
        """Ensure source and target are different entities"""
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("source_entity_id and target_entity_id must be different (self-relationships not allowed)")

        return self


class EntityRelationshipUpdate(BaseModel):
    """Request model for updating an entity relationship

    Follows PATCH semantics: only provided fields are updated.
    None/omitted values mean "don't change this field".

    Examples:
        Update strength: EntityRelationshipUpdate(strength=0.8)
        Add metadata: EntityRelationshipUpdate(metadata={"role": "Team Lead", "promoted": "2025-01-15"})
    """
    relationship_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.ENTITY_RELATIONSHIP_TYPE_MAX_LENGTH,
        description="New relationship type. Unchanged if null."
    )
    strength: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="New strength. Unchanged if null."
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="New confidence. Unchanged if null."
    )
    metadata: Dict[str, Any] | None = Field(
        default=None,
        description="New metadata (replaces existing). Unchanged if null. Empty dict {} clears metadata."
    )

    @field_validator("relationship_type")
    @classmethod
    def strip_whitespace(cls, v):
        """Strip whitespace from relationship_type"""
        if v is None:
            return v

        stripped = v.strip()
        if not stripped:
            raise ValueError("relationship_type cannot be empty or whitespace only")

        return stripped


class EntityRelationship(EntityRelationshipCreate):
    """Complete entity relationship model with generated fields

    Extends EntityRelationshipCreate with system-generated fields (id, timestamps).
    Used for responses that include full relationship details.

    Returned by:
    - create_entity_relationship: After successfully creating a relationship
    - get_entity_relationships: When retrieving relationships for an entity
    - update_entity_relationship: After successfully updating a relationship
    """
    id: int = Field(
        ...,
        description="Unique relationship identifier (auto-generated)"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the relationship was created (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the relationship was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)
