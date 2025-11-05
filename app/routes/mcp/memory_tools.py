"""
MCP Memory tools - FastMCP tool definitions for memory operations
"""
from typing import Any, List

from fastmcp import FastMCP

from app.models.memory_models import (
    Memory, 
    MemoryCreate,
    MemoryUpdate, 
    MemorySummary, 
    MemoryQueryRequest,
    MemoryLinkRequest,
    MemoryQueryResult,
)
from app.middleware.auth import get_user_from_auth
from app.config.logging_config import logging
from app.exceptions import NotFoundError

logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
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
        code_artifacts_ids: List[int] = None,
        document_ids: List[int] = None
    ) -> Memory:   
        pass 
