"""
MCP Document tools - FastMCP tool definitions for document operations
"""
from typing import List

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.models.document_models import (
    Document,
    DocumentCreate,
    DocumentUpdate
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import filter_none_values

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register document tools - services accessed via context at call time"""

    @mcp.tool()
    async def create_document(
        title: str,
        description: str,
        content: str,
        ctx: Context,
        document_type: str = "text",
        filename: str = None,
        tags: List[str] = None,
        project_id: int = None,
    ) -> Document:
        """
        Create document for storing long-form content and documentation.

        WHAT: Stores long-form text like documentation, reports, meeting notes,
        analysis, and prose with metadata. Projects and memories can reference these
        for detailed context and knowledge management.

        WHEN: When documenting detailed information, architectural decisions, analysis,
        meeting notes, or any long-form content (>300 words) that should be referenced
        by memories. Examples:
        - Architecture documentation
        - Meeting notes
        - Analysis reports
        - Design specifications
        - Onboarding guides

        BEHAVIOR: Creates document with provided content and metadata. Can be associated
        with a project immediately via project_id. Returns complete document with generated ID.
        To link to memories, use create_memory or update_memory with document_ids=[document_id].

        After creating a document with detailed content, extract 3-7 atomic memories
        that capture key concepts and link them to this document for discoverability.

        NOT-USE: For short notes or facts <300 words (use memory content directly),
        code snippets (use create_code_artifact), or temporary information.

        EXAMPLES:
        create_document(
            title="Microservices Architecture Overview",
            description="High-level architecture documentation for the microservices platform",
            content="# Architecture\n\n## Overview\nOur platform uses...",
            document_type="markdown",
            tags=["architecture", "design", "microservices"]
        )

        create_document(
            title="Q1 2025 Planning Meeting Notes",
            description="Strategic planning session with engineering leadership",
            content="Attendees: Alice, Bob, Carol\n\nKey Decisions:\n1. Migration to Kubernetes...",
            document_type="text",
            tags=["meeting-notes", "planning", "q1-2025"]
        )

        Args:
            title: Document title (max 500 chars) - searchable identifier
            description: Document's purpose and summary
            content: Complete document text content (markdown, plain text, etc.)
            document_type: Format type (e.g., 'markdown', 'text', 'report', 'notes'). Default: 'text'
            filename: Original filename if imported (metadata only)
            tags: Optional tags for discovery and categorization (max 10)
            project_id: Optional project ID for immediate association
            ctx: Context (automatically injected by FastMCP)

        Returns:
            Complete Document with ID, timestamps, size_bytes, and metadata
        """

        logger.info("MCP Tool Called -> create_document", extra={
            "title": title[:50],
            "document_type": document_type
        })

        user = await get_user_from_auth(ctx)

        try:
            document_data = DocumentCreate(
                title=title,
                description=description,
                content=content,
                document_type=document_type,
                filename=filename,
                tags=tags or [],
                project_id=project_id
            )
        except ValidationError as e:
            raise ToolError(f"Invalid document data: {e}")

        try:
            document_service = ctx.fastmcp.document_service
            document = await document_service.create_document(
                user_id=user.id,
                document_data=document_data
            )

            return document

        except Exception as e:
            logger.error("Failed to create document", exc_info=True)
            raise ToolError(f"Failed to create document: {str(e)}")

    @mcp.tool()
    async def get_document(
        document_id: int,
        ctx: Context
    ) -> Document:
        """
        Retrieve document by ID with complete content.

        WHEN: You need the full document content and metadata for a specific document.
        Common after listing documents or when a memory references a document ID.

        BEHAVIOR: Returns complete document including full content, description,
        and metadata. Ownership verified automatically.

        NOT-USE: For browsing multiple documents (use list_documents).

        Args:
            document_id: Unique document ID
            ctx: Context (automatically injected)

        Returns:
            Complete Document with content, description, metadata

        Raises:
            ToolError if document not found or access denied
        """

        logger.info("MCP Tool Called -> get_document", extra={
            "document_id": document_id
        })

        user = await get_user_from_auth(ctx)

        try:
            document_service = ctx.fastmcp.document_service
            document = await document_service.get_document(
                user_id=user.id,
                document_id=document_id
            )

            return document

        except NotFoundError:
            raise ToolError(f"Document {document_id} not found")
        except Exception as e:
            logger.error("Failed to get document", exc_info=True)
            raise ToolError(f"Failed to retrieve document: {str(e)}")

    @mcp.tool()
    async def list_documents(
        ctx: Context,
        project_id: int = None,
        document_type: str = None,
        tags: List[str] = None,
    ) -> dict:
        """
        List documents with optional filtering.

        WHEN: Browsing available documents, searching for specific content,
        or discovering documents by type/category.

        BEHAVIOR: Returns lightweight summaries (excludes full content) sorted
        by creation date (newest first). Filters can be combined:
        - project_id: Only documents in this project
        - document_type: Only documents of this type (e.g., 'markdown', 'report')
        - tags: Documents with ANY of these tags

        NOT-USE: When you already have a document ID and need full content (use get_document).

        EXAMPLES:
        - All markdown docs: list_documents(document_type="markdown")
        - Meeting notes in project: list_documents(project_id=5, tags=["meeting-notes"])
        - Architecture docs: list_documents(tags=["architecture", "design"])

        Args:
            project_id: Optional filter by project
            document_type: Optional filter by type (e.g., 'markdown', 'text', 'report')
            tags: Optional filter by tags (returns documents with ANY of these tags)
            ctx: Context (automatically injected)

        Returns:
            {
                "documents": List[DocumentSummary],
                "total_count": int,
                "filters": {
                    "project_id": int | None,
                    "document_type": str | None,
                    "tags": List[str] | None
                }
            }
        """

        logger.info("MCP Tool Called -> list_documents", extra={
            "project_id": project_id,
            "document_type": document_type,
            "tags": tags
        })

        user = await get_user_from_auth(ctx)

        try:
            document_service = ctx.fastmcp.document_service
            documents = await document_service.list_documents(
                user_id=user.id,
                project_id=project_id,
                document_type=document_type,
                tags=tags
            )

            return {
                "documents": documents,
                "total_count": len(documents),
                "filters": {
                    "project_id": project_id,
                    "document_type": document_type,
                    "tags": tags
                }
            }

        except Exception as e:
            logger.error("Failed to list documents", exc_info=True)
            raise ToolError(f"Failed to list documents: {str(e)}")

    @mcp.tool()
    async def update_document(
        document_id: int,
        ctx: Context,
        title: str = None,
        description: str = None,
        content: str = None,
        document_type: str = None,
        filename: str = None,
        tags: List[str] = None,
        project_id: int = None,
    ) -> Document:
        """
        Update document (PATCH semantics - only provided fields changed).

        WHEN: Refining content, correcting errors, updating metadata,
        changing categorization, or associating with different project.

        BEHAVIOR: Updates only the fields you provide. Omitted fields remain unchanged.
        - Omit a field = no change
        - Provide new value = replace
        - tags=[] = clear all tags
        - size_bytes automatically recalculated if content changes

        NOT-USE: Creating new documents (use create_document).

        EXAMPLES:
        - Fix typo: update_document(document_id=5, content="corrected content...")
        - Update metadata: update_document(document_id=5, description="New description")
        - Add tags: update_document(document_id=5, tags=["tag1", "tag2", "tag3"])

        Args:
            document_id: Document ID to update
            title: New title (unchanged if omitted)
            description: New description (unchanged if omitted)
            content: New content (unchanged if omitted, auto-updates size_bytes)
            document_type: New document type (unchanged if omitted)
            filename: New filename (unchanged if omitted)
            tags: New tags (unchanged if omitted, empty list [] clears tags)
            project_id: New project association (unchanged if omitted)
            ctx: Context (automatically injected)

        Returns:
            Updated Document

        Raises:
            ToolError if document not found or update fails
        """

        logger.info("MCP Tool Called -> update_document", extra={
            "document_id": document_id
        })

        user = await get_user_from_auth(ctx)

        try:
            # Build update dict, filtering out None values for PATCH semantics
            update_dict = filter_none_values(
                title=title,
                description=description,
                content=content,
                document_type=document_type,
                filename=filename,
                tags=tags,
                project_id=project_id
            )

            # Build update model with only provided fields
            update_data = DocumentUpdate(**update_dict)
        except ValidationError as e:
            raise ToolError(f"Invalid update data: {e}")

        try:
            document_service = ctx.fastmcp.document_service
            document = await document_service.update_document(
                user_id=user.id,
                document_id=document_id,
                document_data=update_data
            )

            return document

        except NotFoundError:
            raise ToolError(f"Document {document_id} not found")
        except Exception as e:
            logger.error("Failed to update document", exc_info=True)
            raise ToolError(f"Failed to update document: {str(e)}")

    @mcp.tool()
    async def delete_document(
        document_id: int,
        ctx: Context
    ) -> dict:
        """
        Delete document (cascades memory associations).

        WHEN: Removing obsolete, incorrect, or no-longer-relevant documents.

        BEHAVIOR: Permanently deletes document and removes memory associations.
        Memories themselves are preserved. Cannot be undone.

        NOT-USE: For temporary hiding (no undo available), or updating (use update_document).

        Args:
            document_id: Document ID to delete
            ctx: Context (automatically injected)

        Returns:
            Success confirmation with deleted document ID

        Raises:
            ToolError if document not found
        """

        logger.info("MCP Tool Called -> delete_document", extra={
            "document_id": document_id
        })

        user = await get_user_from_auth(ctx)

        try:
            document_service = ctx.fastmcp.document_service
            success = await document_service.delete_document(
                user_id=user.id,
                document_id=document_id
            )

            if not success:
                raise ToolError(f"Document {document_id} not found")

            return {"deleted_id": document_id}

        except Exception as e:
            logger.error("Failed to delete document", exc_info=True)
            raise ToolError(f"Failed to delete document: {str(e)}")
