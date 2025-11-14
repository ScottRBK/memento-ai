"""
Unit tests for ToolRegistry

Tests the registry methods in isolation without external dependencies.
"""
import pytest
from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import ToolCategory, ToolParameter


@pytest.fixture
def empty_registry():
    """Provides an empty ToolRegistry for testing"""
    return ToolRegistry()


@pytest.fixture
async def sample_tool_impl():
    """Sample async function for testing tool registration"""
    async def sample_tool(arg1: str, arg2: int = 5):
        return {"arg1": arg1, "arg2": arg2}
    return sample_tool


@pytest.mark.asyncio
async def test_registry_initialization(empty_registry):
    """Test that registry initializes empty"""
    assert len(empty_registry.list_all_tools()) == 0
    assert empty_registry.list_categories() == {}


@pytest.mark.asyncio
async def test_register_tool(empty_registry, sample_tool_impl):
    """Test registering a single tool"""
    params = [
        ToolParameter(
            name="arg1",
            type="str",
            description="First argument",
            required=True,
            example="test"
        ),
        ToolParameter(
            name="arg2",
            type="int",
            description="Second argument",
            required=False,
            default=5,
            example=10
        ),
    ]

    empty_registry.register(
        name="test_tool",
        category=ToolCategory.MEMORY,
        description="A test tool",
        parameters=params,
        returns="Dict with arguments",
        implementation=sample_tool_impl,
        examples=["test_tool('hello', 10)"],
        tags=["test", "sample"],
    )

    assert empty_registry.tool_exists("test_tool")
    assert len(empty_registry.list_all_tools()) == 1


@pytest.mark.asyncio
async def test_get_tool(empty_registry, sample_tool_impl):
    """Test retrieving a registered tool"""
    params = [
        ToolParameter(
            name="arg1",
            type="str",
            description="Test arg",
            required=True
        )
    ]

    empty_registry.register(
        name="retrieve_me",
        category=ToolCategory.USER,
        description="Test retrieval",
        parameters=params,
        returns="Test result",
        implementation=sample_tool_impl,
    )

    tool = empty_registry.get_tool("retrieve_me")
    assert tool is not None
    assert tool.metadata.name == "retrieve_me"
    assert tool.metadata.category == ToolCategory.USER
    assert tool.implementation == sample_tool_impl


@pytest.mark.asyncio
async def test_get_nonexistent_tool(empty_registry):
    """Test retrieving a tool that doesn't exist"""
    tool = empty_registry.get_tool("nonexistent")
    assert tool is None


@pytest.mark.asyncio
async def test_list_all_tools(empty_registry, sample_tool_impl):
    """Test listing all registered tools"""
    params = [ToolParameter(name="test", type="str", description="test", required=True)]

    for i in range(3):
        empty_registry.register(
            name=f"tool_{i}",
            category=ToolCategory.MEMORY,
            description=f"Tool {i}",
            parameters=params,
            returns="Result",
            implementation=sample_tool_impl,
        )

    tools = empty_registry.list_all_tools()
    assert len(tools) == 3
    assert all(tool.name.startswith("tool_") for tool in tools)


@pytest.mark.asyncio
async def test_list_by_category(empty_registry, sample_tool_impl):
    """Test filtering tools by category"""
    params = [ToolParameter(name="test", type="str", description="test", required=True)]

    # Register tools in different categories
    for i in range(2):
        empty_registry.register(
            name=f"memory_tool_{i}",
            category=ToolCategory.MEMORY,
            description="Memory tool",
            parameters=params,
            returns="Result",
            implementation=sample_tool_impl,
        )

    for i in range(3):
        empty_registry.register(
            name=f"user_tool_{i}",
            category=ToolCategory.USER,
            description="User tool",
            parameters=params,
            returns="Result",
            implementation=sample_tool_impl,
        )

    memory_tools = empty_registry.list_by_category(ToolCategory.MEMORY)
    user_tools = empty_registry.list_by_category(ToolCategory.USER)

    assert len(memory_tools) == 2
    assert len(user_tools) == 3
    assert all(tool.category == ToolCategory.MEMORY for tool in memory_tools)
    assert all(tool.category == ToolCategory.USER for tool in user_tools)


@pytest.mark.asyncio
async def test_list_categories(empty_registry, sample_tool_impl):
    """Test getting category counts"""
    params = [ToolParameter(name="test", type="str", description="test", required=True)]

    empty_registry.register(
        name="memory_tool",
        category=ToolCategory.MEMORY,
        description="Memory",
        parameters=params,
        returns="Result",
        implementation=sample_tool_impl,
    )

    empty_registry.register(
        name="user_tool",
        category=ToolCategory.USER,
        description="User",
        parameters=params,
        returns="Result",
        implementation=sample_tool_impl,
    )

    empty_registry.register(
        name="another_memory_tool",
        category=ToolCategory.MEMORY,
        description="Memory",
        parameters=params,
        returns="Result",
        implementation=sample_tool_impl,
    )

    categories = empty_registry.list_categories()
    assert categories["memory"] == 2
    assert categories["user"] == 1
    assert len(categories) == 2


@pytest.mark.asyncio
async def test_tool_exists(empty_registry, sample_tool_impl):
    """Test checking tool existence"""
    params = [ToolParameter(name="test", type="str", description="test", required=True)]

    empty_registry.register(
        name="existing_tool",
        category=ToolCategory.MEMORY,
        description="Exists",
        parameters=params,
        returns="Result",
        implementation=sample_tool_impl,
    )

    assert empty_registry.tool_exists("existing_tool") is True
    assert empty_registry.tool_exists("nonexistent_tool") is False


@pytest.mark.asyncio
async def test_execute_tool(empty_registry):
    """Test executing a registered tool"""
    async def add_numbers(a: int, b: int) -> int:
        return a + b

    params = [
        ToolParameter(name="a", type="int", description="First number", required=True),
        ToolParameter(name="b", type="int", description="Second number", required=True),
    ]

    empty_registry.register(
        name="add",
        category=ToolCategory.MEMORY,
        description="Add two numbers",
        parameters=params,
        returns="Sum",
        implementation=add_numbers,
    )

    result = await empty_registry.execute("add", {"a": 5, "b": 3})
    assert result == 8


@pytest.mark.asyncio
async def test_execute_nonexistent_tool(empty_registry):
    """Test executing a tool that doesn't exist raises ValueError"""
    with pytest.raises(ValueError, match="Tool 'nonexistent' not found in registry"):
        await empty_registry.execute("nonexistent", {})


@pytest.mark.asyncio
async def test_execute_tool_with_context(empty_registry):
    """Test executing a tool with additional context"""
    async def tool_with_context(arg: str, user_id: int = None) -> dict:
        return {"arg": arg, "user_id": user_id}

    params = [
        ToolParameter(name="arg", type="str", description="Argument", required=True),
    ]

    empty_registry.register(
        name="context_tool",
        category=ToolCategory.MEMORY,
        description="Tool with context",
        parameters=params,
        returns="Result with context",
        implementation=tool_with_context,
    )

    result = await empty_registry.execute(
        "context_tool",
        {"arg": "test"},
        user_id=42
    )
    assert result["arg"] == "test"
    assert result["user_id"] == 42


@pytest.mark.asyncio
async def test_register_overwrites_existing(empty_registry, sample_tool_impl):
    """Test that re-registering a tool overwrites the existing one"""
    params = [ToolParameter(name="test", type="str", description="test", required=True)]

    # Register initial tool
    empty_registry.register(
        name="overwrite_me",
        category=ToolCategory.MEMORY,
        description="Original",
        parameters=params,
        returns="Original result",
        implementation=sample_tool_impl,
    )

    # Re-register with different description
    empty_registry.register(
        name="overwrite_me",
        category=ToolCategory.USER,
        description="Updated",
        parameters=params,
        returns="Updated result",
        implementation=sample_tool_impl,
    )

    tool = empty_registry.get_tool("overwrite_me")
    assert tool.metadata.description == "Updated"
    assert tool.metadata.category == ToolCategory.USER
    assert len(empty_registry.list_all_tools()) == 1  # Still only one tool


@pytest.mark.asyncio
async def test_execute_tool_with_optional_parameters(empty_registry):
    """Test executing a tool with optional parameters"""
    async def tool_with_defaults(
        required: str,
        optional: int = 10,
        another: str = "default"
    ) -> dict:
        return {
            "required": required,
            "optional": optional,
            "another": another
        }

    params = [
        ToolParameter(
            name="required",
            type="str",
            description="Required param",
            required=True
        ),
        ToolParameter(
            name="optional",
            type="int",
            description="Optional param",
            required=False,
            default=10
        ),
        ToolParameter(
            name="another",
            type="str",
            description="Another optional",
            required=False,
            default="default"
        ),
    ]

    empty_registry.register(
        name="optional_tool",
        category=ToolCategory.MEMORY,
        description="Tool with optional params",
        parameters=params,
        returns="Result dict",
        implementation=tool_with_defaults,
    )

    # Test with only required parameter
    result1 = await empty_registry.execute(
        "optional_tool",
        {"required": "test"}
    )
    assert result1["required"] == "test"
    assert result1["optional"] == 10
    assert result1["another"] == "default"

    # Test with all parameters
    result2 = await empty_registry.execute(
        "optional_tool",
        {"required": "test2", "optional": 20, "another": "custom"}
    )
    assert result2["required"] == "test2"
    assert result2["optional"] == 20
    assert result2["another"] == "custom"
