"""
End-to-end tests for MCP user tools via HTTP

Requires:
- PostgreSQL running in Docker
- MCP server running on configured port

Tests the complete stack: HTTP → FastMCP Client → MCP Protocol → Service → Repository → PostgreSQL
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_current_user_e2e(docker_services, mcp_server_url):
    """Test get_current_user MCP tool via HTTP transport"""
    async with Client(mcp_server_url) as client:
        # Call MCP tool using FastMCP Client
        result = await client.call_tool("get_current_user", {})

        # FastMCP tools return structured data in result.data
        data = result.data

        assert data["success"] is True
        assert "data" in data
        assert data["data"]["external_id"] is not None
        assert data["data"]["name"] is not None
        assert data["data"]["email"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_user_notes_e2e(docker_services, mcp_server_url):
    """Test update_user_notes MCP tool via HTTP transport"""
    async with Client(mcp_server_url) as client:
        # First, get current user
        get_result = await client.call_tool("get_current_user", {})
        user_data = get_result.data["data"]

        # Update notes using MCP tool
        update_result = await client.call_tool(
            "update_user_notes",
            {"user_notes": "Test notes from E2E test"}
        )

        updated_data = update_result.data

        assert updated_data["success"] is True
        assert updated_data["data"]["notes"] == "Test notes from E2E test"
        assert updated_data["data"]["id"] == user_data["id"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_user_persistence_e2e(docker_services, mcp_server_url):
    """Test that user data persists across multiple MCP tool calls via HTTP transport"""
    async with Client(mcp_server_url) as client:
        # First call - creates user
        result1 = await client.call_tool("get_current_user", {})
        user1 = result1.data["data"]

        # Second call - should return same user
        result2 = await client.call_tool("get_current_user", {})
        user2 = result2.data["data"]

        assert user1["id"] == user2["id"]
        assert user1["external_id"] == user2["external_id"]
        assert user1["created_at"] == user2["created_at"]
