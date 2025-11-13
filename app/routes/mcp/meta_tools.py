"""
MCP - Meta-Tools
This module implements the meta-tools pattern as an alternative to bloating the context window of an LLM with all the tools available
within the MCP service. Instead of loading all tool definitions upfront, we only expose 2 meta-tools.

The two meta-tools:
1. discover_forgetful_tools: List available tools by category, with enough info to allow most LLMs one-shot usage
2. how_to_use_forgetful_tool: Get detailed documentation for a specific tool

Note: execute_forgetful_tool is NOT implemented. FastMCP's native tools/call handles execution with proper schema validation.
"""

from typing import Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from app.config.logging_config import logging
from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import ToolCategory, ToolMetadata, ToolDataDetailed

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, registry: ToolRegistry):
    """Register meta-tools with the provided FastMCP instance"""

    @mcp.tool()
    async def discover_forgetful_tools(
        category: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Discover available Forgetful tools by category

        WHAT: Lists all available tools with summaries for easy understanding and discovery.
        Progressive disclosure pattern - see summaries here, get details with how_to_use_forgetful_tool.

        WHEN: You need to know what tools are available, especially at the start of using Forgetful
        or when looking for tools in a specific area (memory, project, code_artifact, document, linking).

        BEHAVIOR: Returns tool list organized by category. If category specified, filters to just
        that category. Each tool includes name, description, parameters summary, and simple examples.
        Categories: memory (store/query memories), project (organize by context), code_artifact
        (store code snippets), document (long-form docs), linking (connect memories/projects/artifacts).

        NOT-USE: When you already know the exact tool you need and want detailed docs (use how_to_use_forgetful_tool).

        EXAMPLES:
            discover_forgetful_tools() - List all tools across all categories
            discover_forgetful_tools(category="memory") - List only memory tools
            discover_forgetful_tools(category="project") - List only project tools

        Args:
            category: Optional category filter. Options: "memory", "project", "code_artifact",
                     "document", "linking". Omit to get all tools across all categories.

        Returns:
            {
                "tools": List[ToolMetadata] - Tool summaries with name, description, parameters, examples,
                "category": str | None - The category filter applied (if any),
                "total_count": int - Number of tools returned,
                "categories_available": List[str] - All valid category names
            }
        """
        try:
            logger.info("MCP Tool Called -> discover_forgetful_tools", extra={"category": category})

            # Parse and validate category
            filter_category = None
            if category:
                try:
                    filter_category = ToolCategory(category.lower())
                except ValueError:
                    valid_categories = [c.value for c in ToolCategory]
                    raise ToolError(
                        f"Invalid category '{category}'. "
                        f"Valid categories: {', '.join(valid_categories)}"
                    )

            # Get tools from registry
            if filter_category:
                tools = registry.get_by_category(filter_category)
            else:
                # Return all tools across all categories
                all_tools = []
                for cat in ToolCategory:
                    all_tools.extend(registry.get_by_category(cat))
                tools = all_tools

            # Convert to dict for JSON serialization
            tools_dict = [tool.model_dump() for tool in tools]

            logger.info(
                "Tool discovery completed",
                extra={"category": category, "tools_found": len(tools)},
            )

            return {
                "tools": tools_dict,
                "category": category,
                "total_count": len(tools),
                "categories_available": [c.value for c in ToolCategory],
            }

        except ToolError:
            raise
        except Exception as e:
            logger.error("Tool discovery failed", exc_info=True)
            raise ToolError(f"Failed to discover tools: {str(e)}")

    @mcp.tool()
    async def how_to_use_forgetful_tool(tool_name: str) -> Dict[str, any]:
        """
        Get detailed documentation and schema for a specific tool

        WHAT: Returns complete documentation including detailed parameter descriptions, JSON schema
        for validation, multiple examples (basic and advanced), and full docstring.

        WHEN: You've identified a tool from discover_forgetful_tools and need to understand exactly
        how to call it, what parameters it takes, what each parameter does, and what it returns.
        Use this before invoking a tool you're unfamiliar with.

        BEHAVIOR: Returns full ToolDataDetailed including:
        - Complete docstring with WHAT/WHEN/BEHAVIOR/NOT-USE sections
        - Parameter descriptions with types and constraints
        - JSON Schema for validation (compatible with MCP protocol)
        - Multiple examples (basic usage + advanced scenarios)
        - Tags for categorization and discovery

        NOT-USE: When you just want to browse available tools (use discover_forgetful_tools).
        When you already know how to use the tool and are ready to invoke it.

        EXAMPLES:
            how_to_use_forgetful_tool(tool_name="create_memory") - Get docs for create_memory tool
            how_to_use_forgetful_tool(tool_name="query_memory") - Get docs for query_memory tool

        Args:
            tool_name: Name of the tool to document (e.g., "create_memory", "query_memory").
                      Use discover_forgetful_tools to see available tool names.

        Returns:
            {
                "name": str - Tool name,
                "category": str - Tool category,
                "description": str - What the tool does,
                "parameters": List[ToolParameter] - Parameter details (name, type, description),
                "returns": str - What the tool returns,
                "examples": List[str] - Basic usage examples,
                "tags": List[str] - Tags for categorization,
                "json_schema": Dict - JSON Schema for parameter validation,
                "further_examples": List[str] - Advanced usage examples
            }
        """
        try:
            logger.info(
                "MCP Tool Called -> how_to_use_forgetful_tool",
                extra={"tool_name": tool_name},
            )

            tool_details = registry.get_detailed(tool_name)

            if not tool_details:
                available = registry.list_all()
                raise ToolError(
                    f"Tool '{tool_name}' not found. "
                    f"Available tools: {', '.join(sorted(available))}"
                )

            logger.info(
                "Tool documentation retrieved",
                extra={"tool_name": tool_name},
            )

            return tool_details.model_dump()

        except ToolError:
            raise
        except Exception as e:
            logger.error("Tool documentation fetch failed", exc_info=True)
            raise ToolError(f"Failed to get tool documentation: {str(e)}")
