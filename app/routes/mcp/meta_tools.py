"""
MCP - Meta-Tools 
This module implements the meta-tools pattern as an alternative to bloating the context window of an LLM with all the tools available
within the MCP service. Instead of loading all tool definitions upfront, we only expose 3 meta-tools. 

The three meta-tools:
1. discover_forgetful_tools: List available tools by category, with enough info to allow most LLMs one-shot usage
2. how_to_use_forgetful_tool: Get detailed documentation for a specific tool
3. execute_forgetful_tool: Dynamically invoke any tool with arguements
"""

from typing import List

from fastmcp import FastMCP

from app.config.logging_config import logging
from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import ToolCategory, ToolMetadata, ToolDataDetailed

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, registry: ToolRegistry): 
    """Register meta-tools with the provided FastMCP instance"""
    
    @mcp.tool()
    async def discover_forgetful_tools(
            category: ToolCategory
    ) -> List[ToolMetadata]:
        pass
    
    @mcp.tool()
    async def how_to_use_forgetful_tool(tool_name: str) -> ToolDataDetailed:
        pass
