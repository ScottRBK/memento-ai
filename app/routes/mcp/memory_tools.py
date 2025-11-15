"""
MCP Memory tools - FastMCP tool definitions for memory operations
"""
from typing import List

from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.models.memory_models import (
    Memory,
    MemoryCreate,
    MemoryCreateResponse,
    MemoryUpdate,
    MemoryQueryRequest,
    MemoryQueryResult,
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.pydantic_helper import filter_none_values
from app.config.settings import settings

logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
    """Register the memory tools - services accessed via context at call time"""
    
    @mcp.tool()
    async def create_memory(
        title: str,
        content: str,
        context: str,
        keywords: List[str],
        tags: List[str],
        importance: int,
        ctx: Context,
        project_ids: List[int] = None,
        code_artifact_ids: List[int] = None,
        document_ids: List[int] = None,
    ) -> MemoryCreateResponse:   
        """
        Create atomic memory with auto-linking and lifecycle management

        WHAT: Stores single concepts (<400 words), auto-links to similar memories. 

        WHEN: Store important facts/decisions/observations, architectual patterns, preferences, observations that will be useful
        to recall when performing similar actions in the future.

        BEHAVIOR: Generates memories and auto links to similar memories. Returns a list of memories to be reviewed for updating
        or to be made obsolete as a result of the new memory -> use the get_memory tool to inspect these. It is your responsiblity to actively maintain and
        curate the memory store.

        NOT-USE: Mega-memories > 400 words (use create_document), making notes on temporary or common knowledge

        EXAMPLES: create_memory(title="TTS preference: XTTS-v2", 
        content="Selected for voice cloning - high quality, low latency",
        context="Implementing voice integration with an AI agent", 
        importance=9, 
        tags=["decision"], 
        keywords=["tts", "voice-cloning"]). 
        
        For artifacts and documents: create code_artifact/create_document first, 
        then link via code_artifact_ids=[id]/document_ids=[id]

        Args:
            title: Memory title (max 200 characters)
            content: Memory context (max 2000 characters, ~300-400 words) - single concept
            context: WHY this memory matters, HOW it relates, WHAT implications (required, max 500 characters)
            keywords: Search Keywords. Accepts array ["key1", "key2"] (max 10)
            tags: Categorisation tags. Accepts array ["tag1", "tag2"] (max 10)
            importance: Score 1-10 (defaults to 7). scoring guide -> 9-10: Personal/foundational, 8-9: Critical solutions,
            7-8: Useful Patterns, 6-7: Milestones, <6 Storing Discouraged. You should auto create memories where importance
            is above >7. 
            project_ids: Project IDs to link. 
            Accepts an array, [1] for singular, [12, 32] for multiple, [] or omit if None
            code_artifacts: Code artifact IDs to link (create code artifact first).
            Accepts an array, [1] for singular, [12, 32] for multiple, [] or omit if None
            document_ids: Document IDs to link (create document first). 
            Accepts an array, [2] for singular, [34, 19] for multiple, [] oir omit if None
            
        Returns:
            {ID, title, linked_memory_ids, project_ids, code_artifact_ids, document_ids} 
            
        """
        
        logger.info("MCP Tool Called -> create memory", extra={
            "title": title
        })

        user = await get_user_from_auth(ctx) 
        
        try:
            memory_data = MemoryCreate(
                title=title,
                content=content,
                context=context,
                keywords=keywords,
                tags=tags,
                importance=importance,
                project_ids=project_ids,
                code_artifact_ids=code_artifact_ids,
                document_ids=document_ids,
            )

            # Access memory service via FastMCP context
            memory_service = ctx.fastmcp.memory_service
            memory, similar_memories = await memory_service.create_memory(
                user_id=user.id,
                memory_data=memory_data
            )

            logger.info("MCP Tool Call -> create memory completed", extra={
                "user_id": user.id,
                "memory_id": memory.id,
                "title": memory.title,
                "linked_memory_ids": memory.linked_memory_ids,
                "similar_memories_count": len(similar_memories)
            })

            return MemoryCreateResponse(
                id=memory.id,
                title=memory.title,
                linked_memory_ids=memory.linked_memory_ids,
                project_ids=memory.project_ids,
                code_artifact_ids=memory.code_artifact_ids,
                document_ids=memory.document_ids,
                similar_memories=similar_memories
            )

        except NotFoundError as e:
            logger.debug("MCP Tool - create_memory validation error", extra={
                "user_id": user.id,
                "title": title[:50],
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - create_memory validation error", extra={
                "user_id": user.id,
                "title": title[:50],
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool - create_memory failed", exc_info=True, extra={
                "user_id": user.id,
                "title": title[:50],
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Memory creation failed - {type(e).__name__}: {str(e)}")
        
    @mcp.tool()
    async def query_memory(
        query: str,
        query_context: str,
        ctx: Context,
        k: int = 3,
        include_links: bool = True,
        max_links_per_primary: int = 5,
        importance_threshold: int = None,
        project_ids: List[int] = None,
        strict_project_filter: bool = False
    ) -> MemoryQueryResult:
        """
        Search across memories 

        WHEN: User asks about past information, wants to recall discussions, needs context from memory system, you are performing a task that you may
        have performed previously and previous knowledge would be useful (for example implementing planning a new solution and requiring architectual
        preferences, or when encountering an issue that you may have previously solved before). Queries: "What did we decide about X?", 
        "Show memories about Y", "Do you remember Z?". Works best for conceptual queries vs exact keywords. Provide query context around the reason for 
        the search to help improve information retrieval ranking results, for example "looking for information on previous implementation of
        serilog in c#" or "User encountered a bug using pytorch libary". 

        BEHAVIOUR: Performs search and returns top-k primary memories ranked by relevance. Along with linked memories (1-hop neighbours), if include_links=True.
        Auto-applies 8000 token budget, truncates if exceeded. 
        When project_id set: strict_project_filter=True limits linked memories to same project only; False (default) allows cross-project pattern discovery.
        Uses query context to perform additional ranking of initial canidate list of queries. 
        
        NOT-USE: Creating memories (user create_memory), listing all without search, retrieving specific ID (use get_memory),
        getting latest project memories (use query_project_memories)
        
        Args:
            query: Natural language query text
            query_context: The context surrounding the reason for your query. 
            k: Number of primary results, default 3, max 20
            include_links: Boolean to indicate whether to include linked emories for context (default: True)
            max_links_per_primary: int to defined the maximum number of linked memories per primary memory (default: 5)
            importance_threshold: Minimum importance 1-10 (optional)
            project_ids: Filter results to one or more projects (optional). Accepts array of integers or None.
            strict_project_filter: Set to true when querying for a specifc project and you want linked memories restricted to that project only.
            False (default) allows cross-project discovery pattern
            
        Returns:
            query: origional query text
            primary_memories: List of primary related memories
            linked_memories: List of linked memories to each of the primary memories
            total_count: int total count of memories
            token_count: token count of retrieved memories
            truncated: boolean to indicate if the memories have been truncated as a result of the token budget
        """  
        
        try:
            logger.info("MCP Tool -> query_memory", extra={
                "query": query[:50],
                "k": k,
                "include_links": include_links
            })

            user = await get_user_from_auth(ctx)
            
            k = max(1, min(k, 20))
            
            if importance_threshold is not None:
                importance_threshold = max(1, min(importance_threshold, 10))
                
           # Access memory service via FastMCP context
            memory_service = ctx.fastmcp.memory_service
            result = await memory_service.query_memory(
                user_id=user.id,
                memory_query=MemoryQueryRequest(
                    query=query,
                    query_context=query_context,
                    k=k,
                    include_links=include_links,
                    token_context_threshold=settings.MEMORY_TOKEN_BUDGET,
                    max_links_per_primary=max_links_per_primary,
                    importance_threshold=importance_threshold,
                    project_ids=project_ids,
                    strict_project_filter=strict_project_filter
                )
            )
            
            logger.info("MCP Tool -> query memory completed", extra={
                "total_memories_returned": result.total_count,
                "token_count": result.token_count
            })
            
            return result
        except NotFoundError as e:
            logger.debug("MCP Tool - query_memory validation error", extra={
                "query": query[:50],
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - query_memory validation error", extra={
                "query": query[:50],
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> query memory failed", exc_info=True, extra={
                "query": query[:50],
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Memory query failed - {type(e).__name__}: {str(e)}")
        
    @mcp.tool()
    async def update_memory(
        memory_id: int,
        ctx: Context,
        title: str | None = None,
        content: str | None = None,
        context: str | None = None,
        keywords: List[str] | None = None,
        tags: List[str] | None = None,
        importance: int | None = None,
        project_ids: List[int] | None = None,
        code_artifact_ids: List[int] | None = None,
        document_ids: List[int] | None = None,
    ) -> Memory:
        """
        Update existing memory fields (PATCH semantics)

        WHEN: You or the User wants to: 
        1. modify memory details, correct information, update importance or refresh context.
        2. modify the link relationship for a memory to a project, code artifact or document 
        
        BEHAVIOUR: Updates specified fields only (PATCH). Returns the full updated memory to allow you to verify the changes.

        Relationship Field Semantics for List fields (keywords, tags, project_ids, code_artifact_ids, document_ids):
        Omit = left unchanged
        [] = clears (remember tags and keywords are mandatory fields for this entity so this is an invalid operation for these two fields)
        New arrays = replaces existing values

        NOT-USE: Creating new memories (use create_memory), retrieving (use get_memory), searching (use query memory)
        marking memories as obsolete (use mark_memory_obsolete)

        Args:
            memory_id: ID to update (required)
            title: New Title (optional)
            content: New content (optional)
            context: New context (optional)
            keywords: New keywords (optional - replaces existing). Accepts array ["key1", "key2"] (max 10), 
            tags: New tags (optional - replaces existing). Accepts array ["tag1", "tag2"] (max 10), 
            importance: New scoire 1-10 (optional)
            project_ids: New project ids to link to (optional - replaces existing links). Accepts array [1] or [1, 3] for multiple
            code_artifact_ids: New code artifact ids to link to (optional - replaces existing links). Accepts array [1] or [1, 3] for multiple
            document_ids: New document ids to link to (optional - replaces existing links). Accepts array [1] or [1, 3] for multiple

        Returns:
            Full memory object following the update
        """
        try:
            logger.info("MCP Tool -> update_memory", extra={"memory_id": memory_id})

            user = await get_user_from_auth(ctx)
        
            if importance is not None:
                importance = max(1, min(importance, 10))
                
            updated_dict = filter_none_values(
                title=title,
                content=content,
                context=context,
                keywords=keywords,
                tags=tags,
                importance=importance,
                project_ids=project_ids,
                code_artifact_ids=code_artifact_ids,
                document_ids=document_ids,
            ) 
            
            updated_memory = MemoryUpdate(**updated_dict)
            
            memory_service = ctx.fastmcp.memory_service
            refreshed_memory = await memory_service.update_memory(
                user_id=user.id,
                memory_id=memory_id,
                updated_memory=updated_memory,
            )
            
            return refreshed_memory

        except NotFoundError as e:
            logger.debug("MCP Tool - update_memory validation error", extra={
                "memory_id": memory_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - update_memory validation error", extra={
                "memory_id": memory_id,
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> update memory failed", exc_info=True, extra={
                "memory_id": memory_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            raise ToolError(f"INTERNAL_ERROR: Memory update failed - {type(e).__name__}: {str(e)}")
        
    @mcp.tool()
    async def link_memories(
        memory_id: int,
        related_ids: List[int],
        ctx: Context,
    ) -> List[int]:
        """
        Manually create bidirectional links between memories

        WHEN: You or the user decide that a memory wants to connect a related concept not caught by auto-linking,
        establish a relationship between memories, or build a knowledge graph structure.

        BEHAVIOUR: Creates a symmetric (bidirectional) links - if A links to B, B automatically links to A
        Prevents duplicate and self linking.

        NOT-USE: Auto-linking during creation (happens automatically in create_memory), retrieving linked memories (use query_memory
        with include_links), unlinking (not supported - use mark obsolete instead)

        Args:
            memory_id: Source memory ID
            related_ids: List of target memory IDs

        Returns:
            List of target memory IDs that were successfully linked
        """
        
        try:
            logger.info("MCP Tool -> link_memories", extra={
                "memory_id": memory_id,
                "related_ids": related_ids
            })

            user = await get_user_from_auth(ctx)
            
            if not related_ids:
                raise ToolError("related_ids cannot be empty")
            
            related_ids = [rid for rid in related_ids if rid !=memory_id]

            if not related_ids:
                raise ToolError("Cannot link memory to itself")
            
            memory_service = ctx.fastmcp.memory_service
            
            links_created = await memory_service.link_memories(
                user_id=user.id,
                memory_id=memory_id,
                related_ids=related_ids,
            )
            
            logger.info("MCP Tool - memories linked", extra={
                "memory_id": memory_id,
                "memories_linked": links_created
            })
            
            return links_created

        except NotFoundError as e:
            logger.debug("MCP Tool - link_memories validation error", extra={
                "memory_id": memory_id,
                "related_ids": related_ids,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - link_memories validation error", extra={
                "memory_id": memory_id,
                "related_ids": related_ids,
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> link memories failed", exc_info=True, extra={
                "memory_id": memory_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            raise ToolError(f"INTERNAL_ERROR: Memory linking failed - {type(e).__name__}: {str(e)}")
        
    @mcp.tool()
    async def get_memory(
        memory_id: int,
        ctx: Context,
    ) -> Memory:
        """
        Retreive complete memory details by ID

        WHEN: You require the full details of a specific memory and you already have an ID, for example from receiving a list of linked memories
        from a project, document or code artifact.

        BEHAVIOUR: Returns the complete memory object or an error if the memory is not found or does not belong to the user

        NOT-USE: Searching for memories using natural language (use query_memory), listing all memories, updating (use update_memory)
        or creating (use create_memory)

        Args:
            memory_id: ID of the memory to retrieve

        Returns:
            Complete memory object, or error if not found or does not belong to the user
        """
        try:
            logger.info("MCP Tool -> get_memory", extra={
                "memory_id": memory_id
            })   
            
            user = await get_user_from_auth(ctx)
            
            memory_service = ctx.fastmcp.memory_service

            memory = await memory_service.get_memory(user_id=user.id, memory_id=memory_id)
            
            logger.info("MCP Tool - succesfully retrieved memory", extra={
                "memory_id": memory.id, 
                "user_id": user.id
            })

            return memory

        except NotFoundError as e:
            logger.debug("MCP Tool - get_memory validation error", extra={
                "memory_id": memory_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - get_memory validation error", extra={
                "memory_id": memory_id,
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> get memory failed", exc_info=True, extra={
                "memory_id": memory_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            raise ToolError(f"INTERNAL_ERROR: Retreiving memory failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def get_recent_memories(
        ctx: Context,
        limit: int = 10,
        project_ids: List[int] = None
    ) -> List[Memory]:
        """
        Retrieve most recent memories by creation timestamp

        WHEN: You want to see what was recently learned, created, or discussed. Useful for getting context on recent
        work, reviewing recent decisions, or understanding what was added to memory recently.

        BEHAVIOR: Returns memories sorted by creation date (newest first). Optionally filter to specific projects.
        Does not use semantic search - purely timestamp-based retrieval. Excludes obsolete memories.

        NOT-USE: Searching for specific topics (use query_memory), getting a specific memory by ID (use get_memory),
        or listing all memories without time constraints.

        Args:
            limit: Number of memories to return (1-100, default 10)
            project_ids: Optional filter to specific projects. Accepts array [1] or [1, 3] for multiple

        Returns:
            List of Memory objects sorted by created_at DESC (newest first)
        """
        try:
            logger.info("MCP Tool -> get_recent_memories", extra={
                "limit": limit,
                "project_ids": project_ids
            })

            user = await get_user_from_auth(ctx)

            # Clamp limit to reasonable range
            limit = max(1, min(limit, 100))

            memory_service = ctx.fastmcp.memory_service
            memories = await memory_service.get_recent_memories(
                user_id=user.id,
                limit=limit,
                project_ids=project_ids
            )

            logger.info("MCP Tool - get_recent_memories completed", extra={
                "count": len(memories),
                "user_id": str(user.id)
            })

            return memories

        except NotFoundError as e:
            logger.debug("MCP Tool - get_recent_memories validation error", extra={
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - get_recent_memories validation error", extra={
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> get_recent_memories failed", exc_info=True, extra={
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            raise ToolError(f"INTERNAL_ERROR: Retrieving recent memories failed - {type(e).__name__}: {str(e)}")

    @mcp.tool()
    async def mark_memory_obsolete(
        memory_id: int,
        reason: str,
        ctx: Context,
        superseded_by: int | None = None,
    ) -> bool:
        """
        Mark a memory as obsolete (soft delete for audit trail)

        WHEN: Memory is outdated, contradicted by newer information, or replaced by better memory. This is a key
        tool for memory management, outdated memories polluting the memory system will hamper your ability to complete your goals.

        BEHAVIOUR: Soft deletes the memory so that they no longer appear in your query memory results. Optional superseeded by will
        link to the superseeding memory, this preserve data integrity while hiding obsolete information.

        NOT-USE: temporary hiding (no undo - mark as obsolete is permanent soft delete), updating information (use update_memory), or
        hard deleting (not supported for audit compliance).

        Args:
            memory_id: ID of the memory to mark as obsolete
            reason: Why this memory is obsolete
            superseded_by: Optional ID of the replacement memory

        Returns:
            boolean value indicating whether or not the memory was successfully deleted
        """
        try:
            logger.info("MCP Tool -> mark_memory_obsolete", extra={
                "memory_id": memory_id,
            })
            
            user = await get_user_from_auth(ctx)

            memory_service = ctx.fastmcp.memory_service
            
            success = await memory_service.mark_memory_obsolete(
                user_id=user.id,
                memory_id=memory_id,
                reason=reason,
                superseded_by=superseded_by
            )
            
            return success

        except NotFoundError as e:
            logger.debug("MCP Tool - mark_memory_obsolete validation error", extra={
                "memory_id": memory_id,
                "error_type": "NotFoundError",
                "error_message": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            error_details = str(e)
            logger.debug("MCP Tool - mark_memory_obsolete validation error", extra={
                "memory_id": memory_id,
                "error_type": "ValidationError",
                "error_message": error_details
            })
            raise ToolError(f"VALIDATION_ERROR: {error_details}")
        except Exception as e:
            logger.error("MCP Tool -> mark_memory_obsolete failed", exc_info=True, extra={
                "memory_id": memory_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            })
            raise ToolError(f"INTERNAL_ERROR: Marking memory obsolete failed - {type(e).__name__}: {str(e)}")
