"""
Tool Registry for Meta-tools

This module provides a registry system for storing tool metadata and implementations,
enabling the meta-tools.
"""
from typing import Dict, List, Optional, Any

from app.models.tool_registry_models import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolImplementation,
)
from app.config.logging_config import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for all tools with metadata and implementations"""

    def __init__(self):
        """Initialize an empty tool registry"""
        self._tools: Dict[str, ToolImplementation] = {}

    def register(
        self,
        name: str,
        category: ToolCategory,
        description: str,
        parameters: List[ToolParameter],
        returns: str,
        implementation: Any,  # Callable[..., Awaitable[Any]]
        examples: List[str] = None,
        tags: List[str] = None,
    ) -> None:
        """
        Register a tool with its metadata and implementation

        Args:
            name: Unique tool name
            category: Tool category for organization
            description: Brief description of what the tool does
            parameters: List of parameter metadata
            returns: Description of return value
            implementation: Async callable that implements the tool
            examples: Example usage strings
            tags: Tags for categorization
        """
        if name in self._tools:
            logger.warning(f"Tool '{name}' already registered, overwriting")

        metadata = ToolMetadata(
            name=name,
            category=category,
            description=description,
            parameters=parameters,
            returns=returns,
            examples=examples or [],
            tags=tags or [],
        )

        self._tools[name] = ToolImplementation(
            metadata=metadata,
            implementation=implementation,
        )

        logger.debug(f"Registered tool: {name} (category: {category.value})")

    def get_tool(self, name: str) -> Optional[ToolImplementation]:
        """
        Retrieve a tool by name

        Args:
            name: Tool name

        Returns:
            ToolImplementation if found, None otherwise
        """
        return self._tools.get(name)

    def list_all_tools(self) -> List[ToolMetadata]:
        """
        List all registered tools

        Returns:
            List of all tool metadata
        """
        return [impl.metadata for impl in self._tools.values()]

    def list_by_category(self, category: ToolCategory) -> List[ToolMetadata]:
        """
        List tools filtered by category

        Args:
            category: Category to filter by

        Returns:
            List of tool metadata in the specified category
        """
        return [
            impl.metadata
            for impl in self._tools.values()
            if impl.metadata.category == category
        ]

    def list_categories(self) -> Dict[str, int]:
        """
        List all categories with tool counts

        Returns:
            Dict mapping category name to count of tools
        """
        categories: Dict[str, int] = {}
        for impl in self._tools.values():
            cat_name = impl.metadata.category.value
            categories[cat_name] = categories.get(cat_name, 0) + 1
        return categories

    def tool_exists(self, name: str) -> bool:
        """
        Check if a tool is registered

        Args:
            name: Tool name

        Returns:
            True if tool exists, False otherwise
        """
        return name in self._tools

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        **context
    ) -> Any:
        """
        Execute a tool by name with provided arguments

        Args:
            name: Tool name
            arguments: Dictionary of arguments to pass to tool
            **context: Additional context to pass (e.g., user_id)

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            Exception: Any exception raised by tool implementation
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry")

        logger.debug(f"Executing tool: {name} with args: {list(arguments.keys())}")

        try:
            # Execute the tool implementation with arguments and context
            result = await tool.implementation(**arguments, **context)
            logger.debug(f"Tool '{name}' executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {e}", exc_info=True)
            raise 
