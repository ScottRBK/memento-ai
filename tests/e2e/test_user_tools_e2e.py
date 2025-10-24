"""
End-to-end tests for MCP user tools via HTTP

Requires:
- PostgreSQL running in Docker
- MCP server running on configured port

Tests the complete stack: HTTP → MCP → Service → Repository → PostgreSQL
"""
import pytest
import httpx


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_current_user_e2e(mcp_server_url, test_database, cleanup_test_users):
    """Test get_current_user MCP tool via HTTP"""
    async with httpx.AsyncClient() as client:
        # Call MCP tool endpoint
        response = await client.post(
            f"{mcp_server_url}/mcp/tools/get_current_user",
            json={}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert data["data"]["external_id"] is not None
        assert data["data"]["name"] is not None
        assert data["data"]["email"] is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_user_notes_e2e(mcp_server_url, test_database, cleanup_test_users):
    """Test update_user_notes MCP tool via HTTP"""
    async with httpx.AsyncClient() as client:
        # First, get current user
        get_response = await client.post(
            f"{mcp_server_url}/mcp/tools/get_current_user",
            json={}
        )
        assert get_response.status_code == 200
        user_data = get_response.json()["data"]

        # Update notes
        update_response = await client.post(
            f"{mcp_server_url}/mcp/tools/update_user_notes",
            json={"user_notes": "Test notes from E2E test"}
        )

        assert update_response.status_code == 200
        updated_data = update_response.json()

        assert updated_data["success"] is True
        assert updated_data["data"]["notes"] == "Test notes from E2E test"
        assert updated_data["data"]["id"] == user_data["id"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_user_persistence_e2e(mcp_server_url, test_database, cleanup_test_users):
    """Test that user data persists across multiple tool calls"""
    async with httpx.AsyncClient() as client:
        # First call - creates user
        response1 = await client.post(
            f"{mcp_server_url}/mcp/tools/get_current_user",
            json={}
        )
        user1 = response1.json()["data"]

        # Second call - should return same user
        response2 = await client.post(
            f"{mcp_server_url}/mcp/tools/get_current_user",
            json={}
        )
        user2 = response2.json()["data"]

        assert user1["id"] == user2["id"]
        assert user1["external_id"] == user2["external_id"]
        assert user1["created_at"] == user2["created_at"]
