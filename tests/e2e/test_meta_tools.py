"""
E2E tests for meta-tools (discover_forgetful_tools and how_to_use_forgetful_tool)

Requires:
- PostgreSQL running in Docker
- MCP server running on configured port

Tests the complete stack: HTTP → FastMCP Client → MCP Protocol → Meta-tools → ToolRegistry
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discover_forgetful_tools_returns_all_tools_without_filter(
    docker_services, mcp_server_url
):
    """Test discovering all tools across all categories"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("discover_forgetful_tools", {})

        # Should have result with tools
        assert result.data is not None
        assert result.data["tools"] is not None
        assert result.data["total_count"] >= 6
        assert result.data["categories_available"] is not None

        # Should list all available categories
        assert "memory" in result.data["categories_available"]
        assert "project" in result.data["categories_available"]
        assert "code_artifact" in result.data["categories_available"]
        assert "document" in result.data["categories_available"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discover_forgetful_tools_filters_by_memory_category(
    docker_services, mcp_server_url
):
    """Test discovering only memory category tools"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("discover_forgetful_tools", {
            "category": "memory"
        })

        # Should return exactly 6 memory tools
        assert result.data is not None
        assert result.data["total_count"] == 6
        assert result.data["category"] == "memory"

        # Extract tool names
        tool_names = [tool["name"] for tool in result.data["tools"]]

        # Verify all 6 memory tools are present
        expected_tools = [
            "create_memory",
            "query_memory",
            "update_memory",
            "link_memories",
            "get_memory",
            "mark_memory_obsolete",
        ]
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"{expected_tool} not found in discovered tools"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discover_forgetful_tools_returns_tool_metadata(
    docker_services, mcp_server_url
):
    """Test that discovered tools include proper metadata"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("discover_forgetful_tools", {
            "category": "memory"
        })

        assert result.data is not None

        # Find create_memory tool
        create_memory_tool = next(
            (t for t in result.data["tools"] if t["name"] == "create_memory"), None
        )
        assert create_memory_tool is not None

        # Verify metadata structure
        assert "name" in create_memory_tool
        assert "category" in create_memory_tool
        assert "description" in create_memory_tool
        assert "parameters" in create_memory_tool
        assert "returns" in create_memory_tool
        assert "examples" in create_memory_tool
        assert "tags" in create_memory_tool

        # Verify it's summary format (no json_schema or further_examples)
        assert "json_schema" not in create_memory_tool
        assert "further_examples" not in create_memory_tool

        # Verify parameters are present
        assert len(create_memory_tool["parameters"]) > 0
        # Check first parameter has proper structure
        param = create_memory_tool["parameters"][0]
        assert "name" in param
        assert "type" in param
        assert "description" in param


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_how_to_use_forgetful_tool_returns_detailed_metadata(
    docker_services, mcp_server_url
):
    """Test getting detailed documentation for a specific tool"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("how_to_use_forgetful_tool", {
            "tool_name": "create_memory"
        })

        assert result.data is not None

        # Verify detailed metadata structure
        assert result.data["name"] == "create_memory"
        assert result.data["category"] == "memory"
        assert "description" in result.data
        assert "parameters" in result.data
        assert "returns" in result.data
        assert "examples" in result.data
        assert "tags" in result.data

        # Verify detailed format includes json_schema and further_examples
        assert "json_schema" in result.data
        assert "further_examples" in result.data

        # Verify JSON schema has proper structure
        assert result.data["json_schema"]["type"] == "object"
        assert "properties" in result.data["json_schema"]
        assert "required" in result.data["json_schema"]

        # Verify schema has title property
        assert "title" in result.data["json_schema"]["properties"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_how_to_use_forgetful_tool_returns_examples(
    docker_services, mcp_server_url
):
    """Test that detailed docs include examples"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("how_to_use_forgetful_tool", {
            "tool_name": "query_memory"
        })

        assert result.data is not None

        # Should have examples
        assert len(result.data["examples"]) > 0
        # Examples should be strings
        assert all(isinstance(ex, str) for ex in result.data["examples"])


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discover_all_memory_tools_individually(
    docker_services, mcp_server_url
):
    """Test that we can get detailed docs for each memory tool"""
    async with Client(mcp_server_url) as client:
        memory_tools = [
            "create_memory",
            "query_memory",
            "update_memory",
            "link_memories",
            "get_memory",
            "mark_memory_obsolete",
        ]

        for tool_name in memory_tools:
            result = await client.call_tool("how_to_use_forgetful_tool", {
                "tool_name": tool_name
            })

            assert result.data is not None, f"Failed to get docs for {tool_name}"

            # Verify basic structure for each tool
            assert result.data["name"] == tool_name
            assert result.data["category"] == "memory"
            assert "json_schema" in result.data
            assert "parameters" in result.data


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_discover_project_category_has_no_tools_yet(
    docker_services, mcp_server_url
):
    """Test that project category returns empty (no metadata registered yet)"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("discover_forgetful_tools", {
            "category": "project"
        })

        assert result.data is not None

        # Project tools exist but have no metadata registered yet
        # So this should return 0 tools
        assert result.data["total_count"] == 0
        assert result.data["category"] == "project"
