"""
Models for Skills

Skills are what make up procedural memory and provide steps and examples
to allow an agent to perform a particular task. Implements a superset of
the Agent Skills open standard (agentskills.io).
"""

import re
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.config.settings import settings


class SkillCreate(BaseModel):
    """Request model for creating a skill

    Skills are what make up procedural memory and provide steps and examples
    to allow an agent to perform a particular task.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=settings.SKILL_NAME_MAX_LENGTH,
        description=(
            "Kebab-case skill name (e.g., 'pdf-processing')."
            " Must match ^[a-z0-9]+(-[a-z0-9]+)*$"
        ),
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=settings.SKILL_DESCRIPTION_MAX_LENGTH,
        description=(
            "What the skill does and when to use it."
            " Gets embedded for semantic search."
        ),
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.SKILL_CONTENT_MAX_LENGTH,
        description="Full SKILL.md body (markdown instructions)."
    )
    license: str | None = Field(
        None,
        max_length=settings.SKILL_LICENSE_MAX_LENGTH,
        description="License identifier (e.g., 'MIT', 'Apache-2.0')."
    )
    compatibility: str | None = Field(
        None,
        max_length=settings.SKILL_COMPATIBILITY_MAX_LENGTH,
        description="Environment requirements (e.g., 'Requires Python 3.14+ and uv')."
    )
    allowed_tools: list[str] | None = Field(
        None,
        description="Tool restrictions (e.g., ['Bash(python:*)', 'Read', 'WebFetch'])."
    )
    metadata: dict | None = Field(
        None,
        description="Custom key-value pairs (author, version, mcp-server, etc.)."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags."
    )
    importance: int = Field(
        7,
        ge=1,
        le=10,
        description="Importance 1-10 (default 7)."
    )
    project_id: int | None = Field(
        None,
        description="Optional project association."
    )

    @field_validator("name")
    @classmethod
    def validate_name_kebab_case(cls, v):
        """Validate name follows kebab-case format per Agent Skills standard."""
        if v is None:
            return None

        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")

        pattern = r"^[a-z0-9]+(-[a-z0-9]+)*$"
        if not re.match(pattern, stripped):
            raise ValueError(
                "name must be kebab-case (lowercase alphanumeric with hyphens, "
                "e.g., 'my-example-skill')"
            )

        return stripped

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags."""
        if not v:
            return []

        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.SKILL_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.SKILL_TAGS_MAX_COUNT} tags allowed")

        return cleaned


class SkillUpdate(BaseModel):
    """Request model for updating a skill.

    Follows PATCH semantics: only provided fields are updated.
    None/omitted values mean 'don't change this field'.
    """
    name: str | None = Field(None, min_length=1, max_length=settings.SKILL_NAME_MAX_LENGTH)
    description: str | None = Field(None, min_length=1, max_length=settings.SKILL_DESCRIPTION_MAX_LENGTH)
    content: str | None = Field(None, min_length=1, max_length=settings.SKILL_CONTENT_MAX_LENGTH)
    license: str | None = Field(None, max_length=settings.SKILL_LICENSE_MAX_LENGTH)
    compatibility: str | None = Field(None, max_length=settings.SKILL_COMPATIBILITY_MAX_LENGTH)
    allowed_tools: list[str] | None = Field(None)
    metadata: dict | None = Field(None)
    tags: list[str] | None = Field(None)
    importance: int | None = Field(None, ge=1, le=10)
    project_id: int | None = Field(None)

    @field_validator("name")
    @classmethod
    def validate_name_kebab_case(cls, v):
        """Validate name follows kebab-case format per Agent Skills standard."""
        if v is None:
            return None

        stripped = v.strip()
        if not stripped:
            raise ValueError("name cannot be empty or whitespace only")

        pattern = r"^[a-z0-9]+(-[a-z0-9]+)*$"
        if not re.match(pattern, stripped):
            raise ValueError(
                "name must be kebab-case (lowercase alphanumeric with hyphens, "
                "e.g., 'my-example-skill')"
            )

        return stripped

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags."""
        if v is None:
            return None

        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.SKILL_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.SKILL_TAGS_MAX_COUNT} tags allowed")

        return cleaned


class Skill(SkillCreate):
    """Complete Skill model with generated fields.

    Extends SkillCreate with system-generated fields (id and timestamps).
    Used for responses that include full Skill detail.
    """
    id: int = Field(..., description="Unique identifier (auto-generated)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    model_config = ConfigDict(from_attributes=True)


class SkillSummary(BaseModel):
    """Lightweight skill summary for list views.

    Excludes content, allowed_tools, metadata, and compatibility
    to minimise context bloat.
    """
    id: int
    name: str
    description: str
    license: str | None
    tags: list[str]
    importance: int
    project_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
