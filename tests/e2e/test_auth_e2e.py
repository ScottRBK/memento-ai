"""
End-to-end tests for authentication flow via HTTP

Tests complete auth flow: HTTP Request → FastMCP → Auth Middleware → User Provisioning

Integration tests (test_auth.py) mock dependencies for fast unit testing.
These E2E tests validate the full stack with real HTTP and database.
"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.e2e
async def test_default_user_provisioning_e2e(mcp_client):
    """
    Test that default user is provisioned when FASTMCP_SERVER_AUTH not set

    This validates:
    - get_user_from_auth() detects no auth configured
    - Default user auto-provisioned on first tool call
    - Same user returned on subsequent calls (idempotency)
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


# TODO: Docker E2E test for auth-enabled mode
#
# Testing auth-enabled mode with Docker requires actual auth infrastructure
# (JWT keys, OAuth server, or introspection endpoint) which cannot be mocked
# because the FastMCP server runs in a separate Docker container.
#
# The SQLite e2e test (test_auth_enabled_user_from_token_sqlite) already validates
# the complete auth flow end-to-end with mocked tokens in the same process.
#
# To test auth-enabled mode with Docker, you would need to:
# 1. Use DOCKER_ENV_OVERRIDE to configure a real auth provider
# 2. Generate valid tokens (e.g., JWT with proper signing keys)
# 3. Send tokens via Authorization header in Client requests
#
# Example approach (if implementing):
#
# DOCKER_ENV_OVERRIDE = {
#     'FASTMCP_SERVER_AUTH': 'fastmcp.server.auth.providers.jwt.JWTVerifier',
#     'FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY': '<PEM-encoded-public-key>',
#     'FASTMCP_SERVER_AUTH_JWT_ALGORITHM': 'RS256',
#     'FASTMCP_SERVER_AUTH_JWT_ISSUER': 'test-issuer',
#     'FASTMCP_SERVER_AUTH_JWT_AUDIENCE': 'forgetful-test'
# }
#
# @pytest.mark.e2e
# @pytest.mark.asyncio
# async def test_auth_enabled_user_from_token_e2e(mcp_client):
#     """Test user provisioned from bearer token (Docker + PostgreSQL)"""
#     # Generate signed JWT with test RSA key pair
#     test_token = generate_test_jwt(
#         private_key=TEST_PRIVATE_KEY,
#         claims={
#             "sub": "azure|postgres-e2e-test",
#             "name": "PostgreSQL E2E Auth User",
#             "email": "e2e-auth@postgres.test",
#             "iss": "test-issuer",
#             "aud": "forgetful-test"
#         }
#     )
#
#     # Send bearer token in request
#     async with Client(mcp_server_url, headers={"Authorization": f"Bearer {test_token}"}) as client:
#         result = await mcp_client.call_tool(
#             "execute_forgetful_tool",
#             {"tool_name": "get_current_user", "arguments": {}}
#         )
#         assert result.data["name"] == "PostgreSQL E2E Auth User"
