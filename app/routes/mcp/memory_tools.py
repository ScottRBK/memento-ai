"""
MCP Memory tools - FastMCP tool definitions for memory operations
"""
from typing import Any, List

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from app.models.memory_models import (
    Memory, 
    MemoryCreate,
    MemoryCreateResponse,
    MemoryUpdate, 
    MemorySummary, 
    MemoryQueryRequest,
    MemoryLinkRequest,
    MemoryQueryResult,
)
from app.services.memory_service import MemoryService
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.utils.input_coercion import coerce_to_int_list, coerce_to_str_list
from app.config.settings import settings

logger = logging.getLogger(__name__)

def register(mcp: FastMCP, service: MemoryService):
    """Register the memory tools with the provided service instance"""
    
    @mcp.tool()
    async def create_memory(
        title: str,
        content: str,
        context: str,
        keywords: Any,
        tags: Any,
        importance: int,
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
            keywords: Search Keywords. Accepts array ["key1", "key2"], single string "key", or comma-separated "key1,key2" (max 10)
            tags: Categorisation tags. Accepts array ["tag1", "tag2"], single string "tag", or comma-separated "tag1,tag2" (max 10)
            importance: Score 1-10 (defaults to 7). scoring guide -> 9-10: Personal/foundational, 8-9: Critical solutions,
            7-8: Useful Patterns, 6-7: Milestones, <6 Storing Discouraged. You should auto create memories where importance
            is above >7. 
            project_ids: Project IDs to link
            code_artifacts: Code artifact IDs to link (create code artifact first)
            document_ids: Document IDs to link (create document first) 
            
        Returns:
            {ID, title, linked_memory_ids, project_ids, code_artifact_ids, document_ids} 
            
        """
        
        logger.info("MCP Tool Called -> create memory", extra={
            "title": title
        })
        
        user = await get_user_from_auth() 
        
        try:
            keywords_coerced = coerce_to_str_list(keywords,required=True,param_name="keywords")
            tags_coerced = coerce_to_str_list(tags, required=True, param_name="tags")
            project_ids_coerced = coerce_to_int_list(project_ids, param_name="project_ids")
            code_artifact_ids_coerced = coerce_to_int_list(code_artifact_ids, param_name="code_artifact_ids")
            document_ids_coerced = coerce_to_int_list(document_ids, param_name="document_ids")

        except ValueError as e:
            raise ToolError(f"COERCION_ERROR: {str(e)}. Use array format (preferred): keywords=['key1', 'key2']"
                            "tags=['tag1', 'tag2']. Strings also accepted: 'key1,key2' or single 'key'")
        
        try:
            memory_data = MemoryCreate(
                title=title,
                content=content,
                context=context,
                keywords=keywords_coerced,
                tags=tags_coerced,
                importance=importance,
                project_ids=project_ids_coerced,
                code_artifact_ids=code_artifact_ids_coerced,
                document_ids=document_ids_coerced
            )
            
            memory, similar_memories = await service.create_memory(
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
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            logger.error("MCP Tool - create_memory validation failed", exc_info=True, extra={
                "user_id": user.id,
                "title": title[:50],
                "validation_errors": str(e)
            })
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except Exception as e:
            logger.error("MCP Tool - create_memory failed", exc_info=True, extra={
                "user_id": user.id,
                "title": title[:50],
                "error_type": type(e).__name__
            })
            raise ToolError(f"INTERNAL_ERROR: Memory creation failed - {type(e).__name__}")
        
    @mcp.tool()
    async def query_memory(
        query: str,
        query_context: str,
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
            project_ids: Filter results to one or more projects (optional)
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

            user = await get_user_from_auth()
            
            k = max(1, min(k, 20))
            
            if importance_threshold:
                importance_threshold = max(1, min(importance_threshold, 10))
                
            try:
                project_ids_coerced = coerce_to_int_list(project_ids, param_name="project_ids")
            except ValueError as e:
                raise ToolError(f"COERCION_ERROR: {str(e)}. Use array format (preferred): keywords=['key1', 'key2']"
                                "tags=['tag1', 'tag2']. Strings also accepted: 'key1,key2' or single 'key'")
                
            result = await service.query_memory(
                user_id=user.id,
                memory_query=MemoryQueryRequest(
                    query=query,
                    query_context=query_context,
                    k=k,
                    include_links=include_links,
                    token_context_threshold=settings.MEMORY_TOKEN_BUDGET,
                    max_links_per_primary=max_links_per_primary,
                    importance_threshold=importance_threshold,
                    project_ids=project_ids_coerced,
                    strict_project_filter=strict_project_filter 
                )
            )
            
            logger.info("MCP Tool -> query memory completed", extra={
                "total_memories_returned": result.total_count,
                "token_count": result.token_count
            })
            
            return result 
        except NotFoundError as e:
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except ValidationError as e:
            raise ToolError(f"VALIDATION_ERROR: {str(e)}")
        except Exception as e:
            logger.error("MCP Tool -> query memory failed", exc_info=True, extra={
                "query": query[:50],
                "error_type": type(e).__name__
            })
            raise ToolError(f"INTERNAL_ERROR: Memory query failed - {type(e).__name__}")
        

        

       