"""
MCP - Meta-Tools
This module implements the meta-tools pattern as an alternative to bloating the context window of an LLM with all the tools available
within the MCP service. Instead of loading all tool definitions upfront, we only expose 3 meta-tools.

The three meta-tools:
1. discover_forgetful_tools: List available tools by category, with enough info to allow most LLMs one-shot usage
2. how_to_use_forgetful_tool: Get detailed documentation for a specific tool
3. execute_forgetful_tool: Dynamically invoke any tool with arguments
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

from app.config.logging_config import logging
from app.models.tool_registry_models import ToolCategory

logger = logging.getLogger(__name__)


def register(mcp: FastMCP):
    """Register meta-tools with the provided FastMCP instance - registry accessed via ctx pattern"""

    @mcp.tool()
    async def discover_forgetful_tools(
        category: Optional[str] = None,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Discover available tools, optionally filtered by category

        Returns enough information for LLMs to call tools directly without needing how_to_use.

        Args:
            category: Optional category filter (user, memory, project, code_artifact, document, entity, linking)
            ctx: FastMCP Context (automatically injected)

        Returns:
            Dictionary with:
            - tools_by_category: Tools grouped by category
            - total_count: Total number of tools
            - categories_available: List of available categories
            - filtered_by: Category filter applied (if any)
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"discover_forgetful_tools: category={category}")

            if category:
                try:
                    cat_enum = ToolCategory(category.lower())
                    tools_metadata = registry.list_by_category(cat_enum)
                    filtered_by = category
                except ValueError:
                    valid_categories = [c.value for c in ToolCategory]
                    raise ToolError(
                        f"Invalid category '{category}'. "
                        f"Available categories: {', '.join(valid_categories)}"
                    )
            else:
                tools_metadata = registry.list_all_tools()
                filtered_by = None

            # Convert to discovery format (minimal metadata)
            tools = [meta.to_discovery_dict() for meta in tools_metadata]

            # Group by category
            tools_by_category = {}
            for tool in tools:
                cat = tool["category"]
                if cat not in tools_by_category:
                    tools_by_category[cat] = []
                tools_by_category[cat].append(tool)

            result = {
                "tools_by_category": tools_by_category,
                "total_count": len(tools),
                "categories_available": list(registry.list_categories().keys()),
                "filtered_by": filtered_by,
            }

            logger.info(f"discover_forgetful_tools: returned {len(tools)} tools")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"discover_forgetful_tools failed: {e}", exc_info=True)
            raise ToolError(f"Failed to discover tools: {str(e)}")

    @mcp.tool()
    async def how_to_use_forgetful_tool(
        tool_name: str,
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Get detailed documentation for a specific tool

        Returns complete documentation including JSON schema, multiple examples, and full parameter details.

        Args:
            tool_name: Name of the tool to get documentation for
            ctx: FastMCP Context (automatically injected)

        Returns:
            Detailed tool documentation with JSON schema
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"how_to_use_forgetful_tool: tool_name={tool_name}")

            tool = registry.get_tool(tool_name)
            if not tool:
                available_tools = [m.name for m in registry.list_all_tools()[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}"
                )

            detailed_info = tool.metadata.to_detailed_dict()
            logger.info(f"how_to_use_forgetful_tool: returned docs for {tool_name}")
            return detailed_info

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"how_to_use_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to get documentation for '{tool_name}': {str(e)}")

    @mcp.tool()
    async def execute_forgetful_tool(
        tool_name: str,
        arguments: Dict[str, Any],
        ctx: Context
    ) -> Any:
        """
        Execute any registered tool dynamically

        This is the primary execution mechanism - works identically to calling tools directly.
        User context is automatically preserved through the ctx parameter.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            ctx: FastMCP Context (automatically injected)

        Returns:
            Tool execution result (format depends on the specific tool)
        """
        try:
            registry = ctx.fastmcp.registry
            logger.info(f"execute_forgetful_tool: {tool_name}, args={list(arguments.keys())}")

            if not registry.tool_exists(tool_name):
                available_tools = [m.name for m in registry.list_all_tools()[:10]]
                raise ToolError(
                    f"Tool '{tool_name}' not found in registry. "
                    f"Available tools (first 10): {', '.join(available_tools)}"
                )

            # Inject context into arguments for adapters to extract user
            arguments['ctx'] = ctx

            # Execute through registry
            result = await registry.execute(
                name=tool_name,
                arguments=arguments
            )

            logger.info(f"execute_forgetful_tool: {tool_name} executed successfully")
            return result

        except ToolError:
            raise
        except Exception as e:
            logger.error(f"execute_forgetful_tool failed for {tool_name}: {e}", exc_info=True)
            raise ToolError(f"Failed to execute '{tool_name}': {str(e)}")
