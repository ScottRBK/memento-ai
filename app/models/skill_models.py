"""
Models for Skills 
"""

import re
from datetime import datetime, timezone

from pydantic import  BaseModel, Field, field_validator

from app.config.settings import settings 

class SkillCreate(BaseModel):
    """Request model for creating a skill
    
    Skills are what make up procedural memory and provide steps and examples to allow an agent to perform a particular task
    """
    name: str = Field(..., max_length=settings.SKILL_NAME_MAX_LENGTH)
    description: str = Field(..., min_length=1, max_length=settings.SKILL_DESCRIPTION_MAX_LENGTH)
    content: str = Field(..., min_length=1, max_length=settings.SKILL_CONTENT_MAX_LENGTH)
    license: str | None = Field(None,max_length=settings.SKILL_LICENCE_MAX_LENGTH)
    compatibility: str | None = Field(None,max_length=settings.SKILL_COMPATABILITY_MAX_LENGTH)
    allowed_tools: list[str] | None = Field(None)
    metadata: dict | None = Field(None)
    tags: list[str] = Field(...)
    importance: int = Field(..., default=7)
    project_id: int | None = Field(None)

    
    @field_validator("name")
    @classmethod 
    def validate_name_kebab_case(cls, v):
        """Validate name follows kebab-case format: ^[a-z0-9]+(-[a-z0-9]+)*$"""
        
        if v is None:
            return None
        
        stripped = v.strip()

        if not stripped:
            raise ValueError("name cannopt be empty or whitespace only")
        
        pattern = r"^[a-z0-9]+(-[a-z0-9]+)*$"
        if not re.match(pattern, stripped):
            raise ValueError("name must be kebab-case (lowercase alphanumeric with hyphengs, eg., 'my-example-skill')")

        return stripped 

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if not v:
            return []

        # Strip whitespace and remove empty strings
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.SKILL_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.SKILL_TAGS_MAX_COUNT} tags allowed")

        return cleaned

class SkillUpdate(BaseModel):
    """Request model for updating a skill 
    
    Follows PATCH smeantics: only provided fields are updated.
    None/ommited values mean "don't change this field"""
    name: str | None  = Field(None, max_length=settings.SKILL_NAME_MAX_LENGTH)
    description: str | None = Field(None, min_length=1, max_length=settings.SKILL_DESCRIPTION_MAX_LENGTH)
    content: str | None = Field(None, min_length=1, max_length=settings.SKILL_CONTENT_MAX_LENGTH)
    license: str | None = Field(None,max_length=settings.SKILL_LICENCE_MAX_LENGTH)
    compatibility: str | None = Field(None,max_length=settings.SKILL_COMPATABILITY_MAX_LENGTH)
    allowed_tools: list[str] | None = Field(None)
    metadata: dict | None = Field(None)
    tags: list[str] | None = Field(None)
    importance: int | None  = Field(None, default=7)    
    project_id: int | None = Field(None)

    
    @field_validator("name")
    @classmethod 
    def validate_name_kebab_case(cls, v):
        """Validate name follows kebab-case format: ^[a-z0-9]+(-[a-z0-9]+)*$"""
        
        if v is None:
            return None
        
        stripped = v.strip()

        if not stripped:
            raise ValueError("name cannopt be empty or whitespace only")
        
        pattern = r"^[a-z0-9]+(-[a-z0-9]+)*$"
        if not re.match(pattern, stripped):
            raise ValueError("name must be kebab-case (lowercase alphanumeric with hyphengs, eg., 'my-example-skill')")

        return stripped 

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if not v:
            return []

        # Strip whitespace and remove empty strings
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.SKILL_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.SKILL_TAGS_MAX_COUNT} tags allowed")

        return cleaned
    
class Skill(SkillCreate):
    """Complete Skill Model with generated fields
    
    Extends SkillCreate with system-generated fields(id and timestamps)
    Used for responses that include full Skill detail
    """
    id: int = Field(..., description="Unique identifier (auto generated)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    
class SkillSummary(BaseModel):
    """Summary class for skills 
    
    Returns just lightweight informaiton on the skills to avoid context bloat"""
    
    id: int 
    name: str
    description: str
    licence: str | None
    tags: list[str]
    project_id: int | None
    create_at: datetime
    updated_at: datetime
    

    

