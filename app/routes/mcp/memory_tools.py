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
            
            memory = await service.create_memory(
                user_id=user.id,
                memory_data=memory_data
            )

            logger.info("MCP Tool Call -> create memory completed", extra={
                "user_id": user.id,
                "memory_id": memory.id,
                "title": memory.title,
                "linked_memory_ids": memory.linked_memory_ids
            })
            
            return MemoryCreateResponse(
                id=memory.id,
                title=memory.title,
                linked_memory_ids=memory.linked_memory_ids,
                project_ids=memory.project_ids,
                code_artifact_ids=memory.code_artifact_ids,
                document_ids=memory.document_ids
            )

        except ValidationError as e:
            logger.error(f"MCP Tool - create_memory failed due to validation error", exc_info=True, extra={
                "user_id": user.id,
                "title": title,
                "content": content[:20],
                "context": context[:20],
                "keywords": keywords,
                "tags": tags,
                "project_ids": project_ids,
                "code_artifacts_ids": code_artifact_ids,
                "document_ids": document_ids
            })
            raise ToolError(f"Failed to create memory: {str(e)}")
        except Exception as e:
            logger.error(f"MCP Tool - create_memory failed", exc_info=True, extra={
                "user_id": user.id,
                "title": title,
                "content": content[:20],
                "context": context[:20],
                "keywords": keywords,
                "tags": tags,
                "project_ids": project_ids,
                "code_artifacts_ids": code_artifact_ids,
                "document_ids": document_ids
            })
            raise ToolError(f"Failed to create memory: {str(e)}")
        
    @mcp.tool()
    async def query_memory(
        query: str,
    ) -> MemoryQueryResult:
        pass
        
        

        

       