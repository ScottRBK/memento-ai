"""
E2E tests for meta-tools (discover_forgetful_tools and how_to_use_forgetful_tool)

Tests the tool discovery system via actual MCP HTTP calls with Docker Compose setup.
"""
import pytest
import httpx


pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
class TestMetaToolsE2E:
    """E2E tests for meta-tool discovery system"""

    async def test_discover_forgetful_tools_returns_all_tools_without_filter(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test discovering all tools across all categories"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Should have result with tools
        assert "tools" in result
        assert "total_count" in result
        assert "categories_available" in result

        # Should have multiple tools (at least 6 memory tools)
        assert result["total_count"] >= 6

        # Should list all available categories
        assert "memory" in result["categories_available"]
        assert "project" in result["categories_available"]
        assert "code_artifact" in result["categories_available"]
        assert "document" in result["categories_available"]

    async def test_discover_forgetful_tools_filters_by_memory_category(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test discovering only memory category tools"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {"category": "memory"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Should return exactly 6 memory tools
        assert result["total_count"] == 6
        assert result["category"] == "memory"

        # Extract tool names
        tool_names = [tool["name"] for tool in result["tools"]]

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

    async def test_discover_forgetful_tools_rejects_invalid_category(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that invalid category returns error"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {"category": "invalid_category"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        # Should return error
        assert response.status_code == 400
        error_data = response.json()
        assert "Invalid category" in error_data.get("detail", "")

    async def test_discover_forgetful_tools_returns_tool_metadata(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that discovered tools include proper metadata"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {"category": "memory"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Find create_memory tool
        create_memory_tool = next(
            (t for t in result["tools"] if t["name"] == "create_memory"), None
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

    async def test_how_to_use_forgetful_tool_returns_detailed_metadata(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test getting detailed documentation for a specific tool"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "how_to_use_forgetful_tool",
                "arguments": {"tool_name": "create_memory"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Verify detailed metadata structure
        assert result["name"] == "create_memory"
        assert result["category"] == "memory"
        assert "description" in result
        assert "parameters" in result
        assert "returns" in result
        assert "examples" in result
        assert "tags" in result

        # Verify detailed format includes json_schema and further_examples
        assert "json_schema" in result
        assert "further_examples" in result

        # Verify JSON schema has proper structure
        assert result["json_schema"]["type"] == "object"
        assert "properties" in result["json_schema"]
        assert "required" in result["json_schema"]

        # Verify schema has title property
        assert "title" in result["json_schema"]["properties"]

    async def test_how_to_use_forgetful_tool_rejects_nonexistent_tool(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that requesting nonexistent tool returns error"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "how_to_use_forgetful_tool",
                "arguments": {"tool_name": "nonexistent_tool"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        # Should return error
        assert response.status_code == 400
        error_data = response.json()
        assert "not found" in error_data.get("detail", "").lower()
        assert "available tools" in error_data.get("detail", "").lower()

    async def test_how_to_use_forgetful_tool_returns_examples(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that detailed docs include examples"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "how_to_use_forgetful_tool",
                "arguments": {"tool_name": "query_memory"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Should have examples
        assert len(result["examples"]) > 0
        # Examples should be strings
        assert all(isinstance(ex, str) for ex in result["examples"])

    async def test_meta_tools_require_authentication(
        self, mcp_client: httpx.AsyncClient
    ):
        """Test that meta-tools require authentication"""

        # Try without token
        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {},
            },
        )

        # Should be unauthorized
        assert response.status_code == 401

    async def test_discover_all_memory_tools_individually(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that we can get detailed docs for each memory tool"""

        memory_tools = [
            "create_memory",
            "query_memory",
            "update_memory",
            "link_memories",
            "get_memory",
            "mark_memory_obsolete",
        ]

        for tool_name in memory_tools:
            response = await mcp_client.post(
                "/mcp/call_tool",
                json={
                    "name": "how_to_use_forgetful_tool",
                    "arguments": {"tool_name": tool_name},
                },
                headers={"Authorization": f"Bearer {test_user_token}"},
            )

            assert response.status_code == 200, f"Failed to get docs for {tool_name}"
            result = response.json()

            # Verify basic structure for each tool
            assert result["name"] == tool_name
            assert result["category"] == "memory"
            assert "json_schema" in result
            assert "parameters" in result

    async def test_discover_project_category_has_no_tools_yet(
        self, mcp_client: httpx.AsyncClient, test_user_token: str
    ):
        """Test that project category returns empty (no metadata registered yet)"""

        response = await mcp_client.post(
            "/mcp/call_tool",
            json={
                "name": "discover_forgetful_tools",
                "arguments": {"category": "project"},
            },
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

        assert response.status_code == 200
        result = response.json()

        # Project tools exist but have no metadata registered yet
        # So this should return 0 tools
        assert result["total_count"] == 0
        assert result["category"] == "project"
