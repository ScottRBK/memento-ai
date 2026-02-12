"""
End-to-end tests for MCP user tools via HTTP

Requires:
- PostgreSQL running in Docker
- MCP server running on configured port

Tests the complete stack: HTTP → FastMCP Client → MCP Protocol → Service → Repository → PostgreSQL
"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

@pytest.mark.e2e
async def test_get_current_user_e2e(mcp_client):
    """Test get_current_user MCP tool via HTTP transport"""
    # Call MCP tool using FastMCP Client
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )

    # Access attributes from Pydantic UserResponse
    assert result.data is not None
    assert result.data["name"] is not None
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.e2e
async def test_update_user_notes_e2e(mcp_client):
    """Test update_user_notes MCP tool via HTTP transport"""
    # First, get current user
    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )
    assert get_result.data is not None
    user_data = get_result.data

    # Update notes using MCP tool
    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_user_notes",
            "arguments": {"user_notes": "Test notes from E2E test"}
        }
    )

    assert update_result.data is not None
    assert update_result.data["notes"] == "Test notes from E2E test"
    assert update_result.data["name"] == user_data["name"]


@pytest.mark.e2e
async def test_user_persistence_e2e(mcp_client):
    """Test that user data persists across multiple MCP tool calls via HTTP transport"""
    # First call - creates user
    result1 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )
    assert result1.data is not None
    user1 = result1.data

    # Second call - should return same user
    result2 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )
    assert result2.data is not None
    user2 = result2.data

    assert user1["name"] == user2["name"]
    assert user1["created_at"] == user2["created_at"]
