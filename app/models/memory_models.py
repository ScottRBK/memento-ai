from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


from app.config.settings import settings

class MemoryCreate(BaseModel):
    """Request model for creating a memory
    
    Follows atomic memory principles (Zettlekasten)
    - ONE concept per memory (easily titled, understood at first glance)
    - for detailed analysis > 300 words, use create_document instead and
    create a smaller memory linking to the document

    Examples:
        Good (atomic): "TTS engine prefernece: XTTS-v2"
        Bad (mega): "Complete TTS evaluation with all pros/cons/results" 
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=settings.MEMORY_TITLE_MAX_LENGTH,
        description=f"Memory title (max {settings.MEMORY_TITLE_MAX_LENGTH}) - Must be easily scannable"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MEMORY_CONTENT_MAX_LENGTH,
        description=f"""Memory content (max {settings.MEMORY_CONTENT_MAX_LENGTH} chars)
        One concept per memory, for detailed analysis > 300 words use create_document instead
        """
    )
    context: str = Field(
    ...,
    max_length=settings.MEMORY_CONTEXT_MAX_LENGTH,
    description=f"""Rich contextual description explaining WHY this memory matters, HOW it relates to other concepts, 
        "and WHAT implications it has. Goes beyond summarizing content—provides semantic depth for 
        "intelligent linking and retrieval in the knowledge graph. "
        "Max {settings.MEMORY_CONTEXT_MAX_LENGTH} chars"""           
    )
    keywords: List[str] = Field (
        default_factory=list,
        description=f"List of keywords for semantic clustering (max {settings.MEMORY_KEYWORDS_MAX_COUNT})" 
    )
    tags: List[str] = Field(
        default_factory=list,
        description=f"List of tags for categorization (max {settings.MEMORY_TAGS_MAX_COUNT})"
    )
    importance: int = Field(
        7, 
        ge=1, 
        le=10, 
        description="""Importance score (1-10).
          9-10: Personal facts/foundational patterns, 
          8-9: Critical solutions/decisions, 
          7-8: Useful patterns/preferences, 
          6-7: Milestones/specific solutions, 
          5-6: Minor context, 
          <5: Discourage""")
    project_ids: Optional[List[int]] =  Field(default=None, description="Associated project IDs")
    
    field_validator("keywords", "tags")
    @classmethod
    def validate_lists(cls, v, info):
        """Ensure the list doesn't contain empty strings and respect max count"""

        if v is None:
            return []
        
        cleaned = [item.strip() for item in v if item.strip()]
        
        field_name = info.field_name
        max_count = settings.MEMORY_KEYWORDS_MAX_COUNT if field_name == "keywords" else settings.MEMORY_TAGS_MAX_COUNT

        if len(cleaned) > max_count:
            raise ValueError(f"Too manu {field_name}" ({len(cleaned)}, max ({max_count})))
        
        return cleaned
        
class MemoryUpdate(BaseModel):
    """Request model for updating a memory"""
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_TITLE_MAX_LENGTH,
        description=f"Memory title (max {settings.MEMORY_TITLE_MAX_LENGTH})",
    )
    content: Optional[str] = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_CONTENT_MAX_LENGTH,
        description=f"Memory content (max {settings.MEMORY_CONTENT_MAX_LENGTH})",
    )
    context: Optional[str] = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_CONTEXT_MAX_LENGTH,
        description=f"""Rich contextual description (WHY/HOW/WHAT).
        Max {settings.MEMORY_CONTEXT_MAX_LENGTH}"""
    ),
    keywords: Optional[List[str]] = Field(
        None,
        description=f"List of keywords (max {settings.MEMORY_KEYWORDS_MAX_COUNT})"
    ),
    tags: Optional[List[str]] = Field(
        None,
        description=f"List of tags (max {settings.MEMORY_TAGS_MAX_COUNT})"
    ),
    importance: Optional[int] = Field(
        None, 
        ge=1, 
        le=10,
        description=""""importance: Importance score 1-10 (default: 7). Scale:
                • 9-10: Personal facts, foundational architectural patterns (always relevant)
                • 8-9: Critical technical solutions, major architectural decisions
                • 7-8: Useful patterns, strong preferences, tool choices
                • 6-7: Project milestones, specific solutions
                • 5-6: Minor context (manual creation only, not auto-suggested)
                • <5: Generally discourage (ephemeral information)
        """),
    project_ids: Optional[List[int]] = Field(None,description="Associated project IDs")

    field_validator("keywords", "tags")
    @classmethod
    def validate_lists(cls, v, info):
        """Ensure the list doesn't contain empty strings and respect max count"""

        if v is None:
            return []
        
        cleaned = [item.strip() for item in v if item.strip()]
        
        field_name = info.field_name
        max_count = settings.MEMORY_KEYWORDS_MAX_COUNT if field_name == "keywords" else settings.MEMORY_TAGS_MAX_COUNT

        if len(cleaned) > max_count:
            raise ValueError(f"Too manu {field_name}" ({len(cleaned)}, max ({max_count})))
        
        return cleaned
    
    class Memory(MemoryCreate):
        id: int
        created_at: datetime
        updated_at: datetime
        
    
    