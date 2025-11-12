"""
Pydantic models for Document entities

Documents store long-form text content, documentation, reports, and analysis
that can be referenced by memories for knowledge management.
"""
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.config.settings import settings


class DocumentCreate(BaseModel):
    """Request model for creating a document

    Documents store long-form content like documentation, reports, meeting notes,
    analysis, and prose that can be linked to memories and projects for context.

    Examples:
        Architecture doc: title="Microservices Architecture Overview", document_type="markdown"
        Meeting notes: title="Q1 Planning Meeting Notes", document_type="text"
        Analysis: title="Performance Analysis Report", document_type="report"
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=settings.DOCUMENT_TITLE_MAX_LENGTH,
        description="Document title - searchable identifier (e.g., 'API Architecture Overview', 'Sprint Retrospective Notes')"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=settings.DOCUMENT_DESCRIPTION_MAX_LENGTH,
        description="Document's purpose and summary. What does this document contain?"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=settings.DOCUMENT_CONTENT_MAX_LENGTH,
        description="Complete document text content (markdown, plain text, etc.)"
    )
    document_type: str | None = Field(
        default="text",
        max_length=100,
        description="Document format type (e.g., 'markdown', 'text', 'report', 'notes', 'analysis')"
    )
    filename: str | None = Field(
        default=None,
        max_length=500,
        description="Original filename if imported (metadata only)"
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Document size in bytes (metadata only, auto-calculated if not provided)"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=settings.DOCUMENT_TAGS_MAX_COUNT,
        description="Tags for categorization and discovery (e.g., ['architecture', 'design', 'api'])"
    )
    project_id: int | None = Field(
        default=None,
        description="Optional project ID for immediate association with a project"
    )

    @field_validator("title", "description", "content", "document_type", "filename")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # Ensure required fields are not empty after stripping
        if info.field_name in ["title", "description", "content"] and not stripped:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")

        return stripped if stripped else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if not v:
            return []

        # Strip whitespace and remove empty strings
        cleaned = [tag.strip() for tag in v if tag and tag.strip()]

        if len(cleaned) > settings.DOCUMENT_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.DOCUMENT_TAGS_MAX_COUNT} tags allowed")

        return cleaned

    @field_validator("size_bytes", mode="before")
    @classmethod
    def calculate_size_bytes(cls, v, info):
        """Auto-calculate size_bytes from content if not provided"""
        if v is not None:
            return v

        # Access content from values if available
        content = info.data.get("content", "")
        if content:
            return len(content.encode('utf-8'))

        return None


class DocumentUpdate(BaseModel):
    """Request model for updating a document

    Follows PATCH semantics: only provided fields are updated.
    None/omitted values mean "don't change this field".

    Examples:
        Update content: DocumentUpdate(content="revised content...")
        Add tags: DocumentUpdate(tags=["tag1", "tag2", "tag3"])
        Change type: DocumentUpdate(document_type="markdown")
    """
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.DOCUMENT_TITLE_MAX_LENGTH,
        description="New title. Unchanged if null."
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.DOCUMENT_DESCRIPTION_MAX_LENGTH,
        description="New description. Unchanged if null."
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=settings.DOCUMENT_CONTENT_MAX_LENGTH,
        description="New content. Unchanged if null."
    )
    document_type: str | None = Field(
        default=None,
        max_length=100,
        description="New document type. Unchanged if null."
    )
    filename: str | None = Field(
        default=None,
        max_length=500,
        description="New filename. Unchanged if null. Empty string clears."
    )
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="New size. Unchanged if null. Auto-calculated from content if content provided."
    )
    tags: List[str] | None = Field(
        default=None,
        max_length=settings.DOCUMENT_TAGS_MAX_COUNT,
        description="New tags (replaces existing). Unchanged if null. Empty list [] clears tags."
    )
    project_id: int | None = Field(
        default=None,
        description="New project association. Unchanged if null."
    )

    @field_validator("title", "description", "content", "document_type", "filename")
    @classmethod
    def strip_whitespace(cls, v, info):
        """Strip whitespace from string fields"""
        if v is None:
            return v

        stripped = v.strip()

        # Don't allow empty after stripping for required fields (if provided)
        if info.field_name in ["title", "description", "content"] and not stripped:
            raise ValueError(f"{info.field_name} cannot be empty or whitespace only")

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

        if len(cleaned) > settings.DOCUMENT_TAGS_MAX_COUNT:
            raise ValueError(f"Maximum {settings.DOCUMENT_TAGS_MAX_COUNT} tags allowed")

        return cleaned


class Document(DocumentCreate):
    """Complete document model with generated fields

    Extends DocumentCreate with system-generated fields (id, timestamps, project_id).
    Used for responses that include full document details.

    Returned by:
    - create_document: After successfully creating a document
    - get_document: When retrieving a specific document by ID
    - update_document: After successfully updating a document
    """
    id: int = Field(
        ...,
        description="Unique document identifier (auto-generated)"
    )
    project_id: int | None = Field(
        default=None,
        description="Associated project ID. Null if not linked to a project."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the document was created (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="When the document was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)


class DocumentSummary(BaseModel):
    """Lightweight document summary for list operations

    Excludes heavy content field to minimize token usage when listing
    multiple documents. Contains just enough info to identify and filter.

    Used by:
    - list_documents: When listing all documents or filtering by project/type/tags
    """
    id: int = Field(
        ...,
        description="Unique document identifier"
    )
    title: str = Field(
        ...,
        description="Document title"
    )
    description: str = Field(
        ...,
        description="Document description"
    )
    document_type: str | None = Field(
        default=None,
        description="Document format type"
    )
    filename: str | None = Field(
        default=None,
        description="Original filename if imported"
    )
    size_bytes: int = Field(
        ...,
        description="Document size in bytes"
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
        description="When the document was created (UTC)"
    )
    updated_at: datetime = Field(
        ...,
        description="When the document was last updated (UTC)"
    )

    model_config = ConfigDict(from_attributes=True)
