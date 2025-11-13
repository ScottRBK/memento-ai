"""
Unit tests for ToolRegistry

Tests the core registry functionality without any external dependencies.
"""
import pytest

from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import (
    ToolCategory,
    ToolDataDetailed,
    ToolMetadata,
    ToolParameter,
)


class TestToolRegistry:
    """Unit tests for ToolRegistry class"""

    def test_init_creates_empty_registry(self):
        """Test that registry initializes with empty tool collections"""
        registry = ToolRegistry()

        assert registry.total_count() == 0
        assert registry.list_all() == []
        for category in ToolCategory:
            assert registry.count_by_category(category) == 0

    def test_register_tool_adds_to_registry(self):
        """Test registering a single tool"""
        registry = ToolRegistry()

        tool_metadata = ToolDataDetailed(
            name="test_tool",
            category=ToolCategory.MEMORY,
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type="str",
                    description="First parameter",
                )
            ],
            returns="str",
            examples=["test_tool(param1='value')"],
            tags=["test"],
            json_schema={"type": "object", "properties": {}},
            further_examples=[],
        )

        registry.register_tool(tool_metadata)

        assert registry.total_count() == 1
        assert "test_tool" in registry.list_all()
        assert registry.count_by_category(ToolCategory.MEMORY) == 1

    def test_register_duplicate_tool_raises_error(self):
        """Test that registering same tool name twice raises ValueError"""
        registry = ToolRegistry()

        tool_metadata = ToolDataDetailed(
            name="test_tool",
            category=ToolCategory.MEMORY,
            description="A test tool",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )

        registry.register_tool(tool_metadata)

        # Try to register same name again
        with pytest.raises(ValueError, match="already registered"):
            registry.register_tool(tool_metadata)

    def test_get_by_category_filters_correctly(self):
        """Test retrieving tools by category"""
        registry = ToolRegistry()

        # Register tools in different categories
        memory_tool = ToolDataDetailed(
            name="memory_tool",
            category=ToolCategory.MEMORY,
            description="Memory tool",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )

        project_tool = ToolDataDetailed(
            name="project_tool",
            category=ToolCategory.PROJECT,
            description="Project tool",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )

        registry.register_tool(memory_tool)
        registry.register_tool(project_tool)

        # Get tools by category
        memory_tools = registry.get_by_category(ToolCategory.MEMORY)
        project_tools = registry.get_by_category(ToolCategory.PROJECT)

        assert len(memory_tools) == 1
        assert len(project_tools) == 1
        assert memory_tools[0].name == "memory_tool"
        assert project_tools[0].name == "project_tool"

    def test_get_by_category_returns_summary_not_detailed(self):
        """Test that get_by_category returns ToolMetadata (not ToolDataDetailed)"""
        registry = ToolRegistry()

        tool_metadata = ToolDataDetailed(
            name="test_tool",
            category=ToolCategory.MEMORY,
            description="A test tool",
            parameters=[],
            returns="str",
            examples=["example1"],
            tags=["tag1"],
            json_schema={"type": "object"},
            further_examples=["advanced_example"],
        )

        registry.register_tool(tool_metadata)

        tools = registry.get_by_category(ToolCategory.MEMORY)

        assert len(tools) == 1
        assert isinstance(tools[0], ToolMetadata)
        # Verify further_examples is excluded (summary format)
        assert not hasattr(tools[0], 'further_examples')

    def test_get_detailed_returns_complete_metadata(self):
        """Test retrieving detailed metadata for a specific tool"""
        registry = ToolRegistry()

        tool_metadata = ToolDataDetailed(
            name="test_tool",
            category=ToolCategory.MEMORY,
            description="A test tool",
            parameters=[],
            returns="str",
            examples=["example1"],
            tags=["tag1"],
            json_schema={"type": "object"},
            further_examples=["advanced_example"],
        )

        registry.register_tool(tool_metadata)

        detailed = registry.get_detailed("test_tool")

        assert detailed is not None
        assert isinstance(detailed, ToolDataDetailed)
        assert detailed.name == "test_tool"
        assert detailed.json_schema == {"type": "object"}
        assert detailed.further_examples == ["advanced_example"]

    def test_get_detailed_returns_none_for_nonexistent_tool(self):
        """Test that getting nonexistent tool returns None"""
        registry = ToolRegistry()

        result = registry.get_detailed("nonexistent_tool")

        assert result is None

    def test_list_all_returns_sorted_names(self):
        """Test that list_all returns sorted list of tool names"""
        registry = ToolRegistry()

        # Register in non-alphabetical order
        for name in ["zebra_tool", "alpha_tool", "beta_tool"]:
            tool = ToolDataDetailed(
                name=name,
                category=ToolCategory.MEMORY,
                description="Test",
                parameters=[],
                returns="str",
                examples=[],
                tags=[],
                json_schema={},
                further_examples=[],
            )
            registry.register_tool(tool)

        tools = registry.list_all()

        assert tools == ["alpha_tool", "beta_tool", "zebra_tool"]

    def test_get_all_categories_returns_all_tools_organized(self):
        """Test get_all_categories returns tools organized by category"""
        registry = ToolRegistry()

        # Register tools in different categories
        memory_tool = ToolDataDetailed(
            name="memory_tool",
            category=ToolCategory.MEMORY,
            description="Memory tool",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )

        project_tool = ToolDataDetailed(
            name="project_tool",
            category=ToolCategory.PROJECT,
            description="Project tool",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )

        registry.register_tool(memory_tool)
        registry.register_tool(project_tool)

        all_categories = registry.get_all_categories()

        assert ToolCategory.MEMORY in all_categories
        assert ToolCategory.PROJECT in all_categories
        assert len(all_categories[ToolCategory.MEMORY]) == 1
        assert len(all_categories[ToolCategory.PROJECT]) == 1
        assert all_categories[ToolCategory.MEMORY][0].name == "memory_tool"
        assert all_categories[ToolCategory.PROJECT][0].name == "project_tool"

    def test_count_by_category_returns_correct_count(self):
        """Test count_by_category returns accurate counts"""
        registry = ToolRegistry()

        # Register 2 memory tools, 1 project tool
        for i in range(2):
            tool = ToolDataDetailed(
                name=f"memory_tool_{i}",
                category=ToolCategory.MEMORY,
                description="Test",
                parameters=[],
                returns="str",
                examples=[],
                tags=[],
                json_schema={},
                further_examples=[],
            )
            registry.register_tool(tool)

        project_tool = ToolDataDetailed(
            name="project_tool",
            category=ToolCategory.PROJECT,
            description="Test",
            parameters=[],
            returns="str",
            examples=[],
            tags=[],
            json_schema={},
            further_examples=[],
        )
        registry.register_tool(project_tool)

        assert registry.count_by_category(ToolCategory.MEMORY) == 2
        assert registry.count_by_category(ToolCategory.PROJECT) == 1
        assert registry.count_by_category(ToolCategory.CODE_ARTIFACT) == 0
