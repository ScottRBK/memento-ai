"""
Tool Registry for Meta-tools

This module provides a registry system for storing tool metadata and implementations,
enabling the meta-tools.
"""
from typing import Dict, List, Optional

from app.models.tool_registry_models import (
    ToolCategory,
    ToolDataDetailed,
    ToolMetadata,
)


class ToolRegistry:
    """
    Central registry for tool metadata and discovery.

    Populated during application startup from all registered tools.
    Enables meta-tools to provide progressive disclosure of available functionality.
    """

    def __init__(self):
        """Initialize empty registry with category indexes"""
        self._tools: Dict[str, ToolDataDetailed] = {}  # name -> metadata
        self._by_category: Dict[ToolCategory, List[str]] = {
            ToolCategory.MEMORY: [],
            ToolCategory.PROJECT: [],
            ToolCategory.CODE_ARTIFACT: [],
            ToolCategory.DOCUMENT: [],
            ToolCategory.LINKING: [],
        }

    def register_tool(self, metadata: ToolDataDetailed) -> None:
        """
        Register a tool with its metadata

        Args:
            metadata: Complete tool metadata including schema and examples

        Raises:
            ValueError: If tool name already registered (prevents accidental overwrite)
        """
        if metadata.name in self._tools:
            raise ValueError(
                f"Tool '{metadata.name}' already registered. "
                "Each tool must have a unique name."
            )

        self._tools[metadata.name] = metadata
        self._by_category[metadata.category].append(metadata.name)

    def get_by_category(self, category: ToolCategory) -> List[ToolMetadata]:
        """
        Get all tools in a category (summary format, not detailed)

        Args:
            category: Tool category to filter by

        Returns:
            List of ToolMetadata (excludes json_schema and further_examples)
        """
        tool_names = self._by_category[category]
        return [
            ToolMetadata(
                **self._tools[name].model_dump(
                    exclude={"json_schema", "further_examples"}
                )
            )
            for name in tool_names
        ]

    def get_all_categories(self) -> Dict[ToolCategory, List[ToolMetadata]]:
        """
        Get all tools organized by category

        Returns:
            Dictionary mapping categories to their tool metadata lists
        """
        return {
            category: self.get_by_category(category)
            for category in ToolCategory
        }

    def get_detailed(self, tool_name: str) -> Optional[ToolDataDetailed]:
        """
        Get complete details for a specific tool

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            Complete ToolDataDetailed or None if not found
        """
        return self._tools.get(tool_name)

    def list_all(self) -> List[str]:
        """
        Get all registered tool names

        Returns:
            Sorted list of all tool names
        """
        return sorted(self._tools.keys())

    def count_by_category(self, category: ToolCategory) -> int:
        """
        Get count of tools in a category

        Args:
            category: Tool category to count

        Returns:
            Number of tools in the category
        """
        return len(self._by_category[category])

    def total_count(self) -> int:
        """
        Get total number of registered tools

        Returns:
            Total tool count across all categories
        """
        return len(self._tools) 
