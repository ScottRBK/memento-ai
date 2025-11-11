from typing import List
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
        description="Concise, scannable title (5-50 words). Examples: 'Python QueueHandler prevents asyncio blocking', 'TTS preference: XTTS-v2'"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.MEMORY_CONTENT_MAX_LENGTH,
        description="ONE concept, self-contained (max ~400 words). If >300 words, use create_document and extract atomic memories instead."
    )
    context: str = Field(
        ...,
        max_length=settings.MEMORY_CONTEXT_MAX_LENGTH,
        description="WHY this matters, HOW it relates to other concepts, WHAT implications. Enables intelligent auto-linking and semantic retrieval."
    )
    keywords: List[str] = Field(
        ...,
        max_length=settings.MEMORY_KEYWORDS_MAX_COUNT,
        description="Search terms for semantic discovery (e.g., 'python', 'asyncio', 'logging'). Max 10."
    )
    tags: List[str] = Field(
        ...,
        max_length=settings.MEMORY_TAGS_MAX_COUNT,
        description="Categories for grouping memories (e.g., 'pattern', 'decision', 'bug-fix'). Max 10."
    )
    importance: int = Field(
        7,
        ge=1,
        le=10,
        description="Importance 1-10 (default 7): 9-10=personal facts/foundational patterns, 8-9=critical solutions/decisions, 7-8=useful patterns/preferences, 6-7=milestones/solutions, <6=discourage."
    )
    project_ids: List[int] | None = Field(
        default=None,
        description="Link to project(s) for scoped queries. Enables 'show memories for Project X' filtering."
    )
    code_artifact_ids: List[int] | None = Field(
        default=None,
        description="Code artifact IDs to link (create artifacts first). Links implementation examples to this memory."
    )
    document_ids: List[int] | None = Field(
        default=None,
        description="Document IDs to link (create documents first). Links detailed analysis/narrative to this atomic memory."
    )

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
            raise ValueError(f"Too many {field_name} ({len(cleaned)}, max {max_count})")
        
        return cleaned
        
class MemoryUpdate(BaseModel):
    """Request model for updating a memory"""
    title: str | None = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_TITLE_MAX_LENGTH,
        description="New title (5-50 words, scannable). Unchanged if null."
    )
    content: str | None = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_CONTENT_MAX_LENGTH,
        description="New content (ONE concept, max ~400 words). Unchanged if null."
    )
    context: str | None = Field(
        None,
        min_length=1,
        max_length=settings.MEMORY_CONTEXT_MAX_LENGTH,
        description="New context (WHY/HOW/WHAT for auto-linking). Unchanged if null."
    )
    keywords: List[str] | None = Field(
        None,
        max_length=settings.MEMORY_KEYWORDS_MAX_COUNT,
        description="New search terms (max 10). Replaces existing if provided, unchanged if null."
    )
    tags: List[str] | None = Field(
        None,
        max_length=settings.MEMORY_TAGS_MAX_COUNT,
        description="New categories (max 10). Replaces existing if provided, unchanged if null."
    )
    importance: int | None = Field(
        None,
        ge=1,
        le=10,
        description="New importance 1-10: 9-10=personal/foundational, 8-9=critical, 7-8=useful, 6-7=milestones, <6=discourage. Unchanged if null."
    )
    project_ids: List[int] | None = Field(
        None,
        description="New project associations. Replaces existing if provided, unchanged if null."
    )
    code_artifact_ids: List[int] | None = Field(
        None,
        description="New code artifact links. Replaces existing if provided, unchanged if null."
    )
    document_ids: List[int] | None = Field(
        None,
        description="New document links. Replaces existing if provided, unchanged if null."
    )


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
            raise ValueError(f"Too many {field_name} ({len(cleaned)}, max {max_count})")
        
        return cleaned
    
class Memory(MemoryCreate):
    id: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    project_ids: List[int] = Field(default_factory=list)
    linked_memory_ids: List[int] = Field(default_factory=list)
    code_artifact_ids: List[int] = Field(default_factory=list, description="Linked code artifact IDs")
    document_ids: List[int] = Field(default_factory=list, description="Linked document IDs")

    # Lifecycle management fields
    is_obsolete: bool = Field(default=False, description="Whether this memory has been marked obsolete")
    obsolete_reason: str | None = Field(default=None, description="Reason why this memory was marked obsolete")
    superseded_by: int | None = Field(default=None, description="ID of memory that supersedes this one")
    obsoleted_at: datetime | None = Field(default=None, description="When this memory was marked obsolete")

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

class MemoryCreateResponse(BaseModel):
    """Lightweight response information to confirm memory creation"""
    id: int
    title: str
    linked_memory_ids: List[int] = Field(default_factory=list)
    project_ids: List[int] = Field(default_factory=list)
    code_artifact_ids: List[int] = Field(default_factory=list)
    document_ids: List[int] = Field(default_factory=list)
    similar_memories: List[MemorySummary] = Field(
        default_factory=list,
        description="Summaries of similar memories that were auto-linked for review"
    )
    
class MemoryQueryRequest(BaseModel):
    """Request model for querying memories"""
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language query for semantic search (e.g., 'Python logging best practices')"
    )
    query_context: str = Field(
        ...,
        min_length=1,
        description="Contextual reasoning behind why you are searching for this information"
    )
    k: int = Field(
        3,
        ge=1,
        le=20,
        description="Number of top semantic matches to return (primary results)"
    )
    include_links: int = Field(
        1,
        ge=0,
        le=5,
        description="Graph traversal depth (0=no links, 1=direct neighbors, 2+=exponential context bloat). Recommended: 0-1."
    )
    token_context_threshold: int = Field(
        8000,
        ge=4000,
        le=25000,
        description="Max tokens before truncating results (8K default fits most LLM contexts)"
    )
    max_links_per_primary: int = Field(
        5,
        ge=0,
        le=10,
        description="Max linked memories per primary result (controls context expansion)"
    )
    importance_threshold: int | None = Field(
        None,
        ge=1,
        le=10,
        description="Filter out memories below this importance (e.g., 7=only important memories)"
    )
    project_ids: List[int] | None = Field(
        None,
        description="Filter results to specific projects (scoped search within project context)"
    )
    strict_project_filter: bool = Field(
        False,
        description="Opt out flag to exlcude memories from being retrieved from outside of the project"
    )
    
class LinkedMemory(BaseModel):
    """Memory with linked context"""
    memory: Memory
    link_source_id: int = Field(..., description="ID of memory this is linked from")
    
    model_config = ConfigDict(from_attributes=True)
    
class MemoryQueryResult(BaseModel):
    """Response Model for memory query"""
    query: str
    primary_memories: List[Memory]
    linked_memories: List[LinkedMemory] = Field(default_factory=list)
    total_count: int
    token_count: int
    truncated: bool = Field(False, description="Whether the results were truncated due to token budget")
    
class MemoryLinkRequest(BaseModel):
    """Request model for linking memories"""
    memory_id: int = Field(..., description="Source memory ID")
    related_ids: List[int] = Field(..., min_length=1, description="Target memory IDs to link")
    
    @field_validator("related_ids")
    @classmethod
    def validate_related_ids(cls, v, info):
        """Ensure memory is not linking to itself"""
        if "memory_id" in info.data and info.data["memory_id"] in v:
            raise ValueError("Cannot link memory to itself")
        return v

        
        
    
    