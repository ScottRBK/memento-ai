from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict


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
    code_artifact_ids: Optional[List[int]] = Field(default=None, description="Code artifact IDs to link (create artifacts first)")
    document_ids: Optional[List[int]] = Field(default=None, description="Document IDs to link (create documents first)")

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
    code_artifact_ids: Optional[List[int]] = Field(default=None, description="Code artifact IDs to link (create artifacts first)")
    document_ids: Optional[List[int]] = Field(default=None, description="Document IDs to link (create documents first)")


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    project_ids: List[int] = Field(default_factory=list)
    linked_memory_ids: List[int] = Field(default_factory=list)
    code_artifact_ids: List[int] = Field(default_factory=list, description="Linked code artifact IDs")
    document_ids: List[int] = Field(default_factory=list, description="Linked document IDs")

    model_config = ConfigDict(from_attributes=True)
    
class MemorySummary(BaseModel):
    """Lightweight memory summary for list views"""
    id: int
    title: str
    keywords: List[str]
    tags: List[str]
    importance: int
    created_at: datetime
    updated_at: datetime 

    model_config = ConfigDict(from_attributes=True)
    
class MemoryQueryRequest(BaseModel):
    """Request model for querying memories"""
    query: str = Field(..., min_length=1, description="Query Text")
    k: int = Field(5, ge=1, le=20, description="Number of primary results")
    included_links: int = Field(1, ge=0, le=5,  description="Number of memory hops to include **CAUTION - CONTEXT BLOAT OVER 1**")
    token_context_threshold: int = Field(8000, ge=4000, le=25000, description="Threshold before context cut off of retrieve memories")
    max_links_per_primary: int = Field(5, ge=0, le=10, description="Maxlinks per primary result")
    importance_threshold: Optional[int] = Field(None, ge=1, le=10, description="Minimum importance score")
    project_id: Optional[int] = Field(None, description="Filter/boost by project")
    
class LinkedMemory(BaseModel):
    """Memory with linked context"""
    memory: Memory
    link_source_id: int = Field(..., description="ID of memory this is linked from")
    
    model_config = ConfigDict(from_attributes=True)
    
class MemoryQueryResult(BaseModel):
    """Response Moddel for memory query"""
    query: str
    primary_memories: List[Memory]
    linked_memories: List[LinkedMemory] = Field(default_factory=list)
    total_count = int
    token_count = int
    truncated: bool = Field(False, description="Whether the results were truncated due to token budget")
    
class MemoryLinkRequest(BaseModel):
    """Request model for linking memories"""
    memory_id: int = Field(..., description="Source memory ID")
    related_ids: List[int] = Field(..., min_length=1, description="Target memory IDs to link")
    
    @field_validator("related_ids")
    @classmethod
    def validate_related_ids(cls, v, info):
        """Ensure memory is not linking to itself"""
        if "memory_id" in info.data and info.data["memory)id"] in v:
            raise ValueError("Cannot link memory to itself")
        return v

        
        
    
    