"""
End-to-end tests for authentication flow with SQLite backend

Tests complete auth flow: FastMCP → Auth Middleware → User Provisioning → SQLite

Integration tests (test_auth.py) mock dependencies for fast unit testing.
These E2E tests validate the full stack with in-process FastMCP and in-memory SQLite.
"""
import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_default_user_provisioning_sqlite(mcp_client):
    """
    Test that default user is provisioned when FASTMCP_SERVER_AUTH not set

    This validates:
    - get_user_from_auth() detects no auth configured
    - Default user auto-provisioned on first tool call
    - Same user returned on subsequent calls (idempotency)
    - Data persisted to SQLite database
    """
    # First tool call - should auto-create default user
    result1 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )

    assert result1.data is not None
    user1_name = result1.data["name"]
    user1_created_at = result1.data["created_at"]

    # Should match default user settings (name contains "default")
    assert "default" in user1_name.lower()

    # Second tool call - should return same user (idempotency)
    result2 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )

    assert result2.data is not None
    # Verify it's the same user by comparing name and created_at
    assert result2.data["name"] == user1_name
    assert result2.data["created_at"] == user1_created_at


class MockAccessToken:
    """Mock AccessToken for testing auth-enabled mode"""
    def __init__(self, claims: dict):
        self.claims = claims


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_user_from_token_sqlite(mock_get_token, mock_getenv, mcp_client):
    """
    Test that user is provisioned from bearer token when auth enabled

    This validates the complete auth flow with real database:
    1. get_user_from_auth() detects auth is configured
    2. Extracts claims from access token
    3. User auto-provisioned from token claims (sub, name, email) to SQLite
    4. Tool execution uses the authenticated user
    5. Multiple calls with same token return same user (from database)
    """
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock access token with test claims
    mock_token = MockAccessToken(claims={
        "sub": "github|sqlite-e2e-test",
        "name": "SQLite E2E Auth User",
        "email": "e2e-auth@sqlite.test"
    })
    mock_get_token.return_value = mock_token

    # First tool call - should auto-provision user from token to database
    result1 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )

    assert result1.data is not None
    # Verify user name from token claim
    assert result1.data["name"] == "SQLite E2E Auth User"
    assert result1.data["created_at"] is not None

    # Second tool call - should return same user from database (idempotency)
    result2 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "get_current_user",
            "arguments": {}
        }
    )

    assert result2.data is not None
    assert result2.data["name"] == "SQLite E2E Auth User"
    # Same created_at proves it's the same user retrieved from DB, not a duplicate
    assert result2.data["created_at"] == result1.data["created_at"]
