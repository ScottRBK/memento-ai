"""
Integration tests for REST API authentication (get_user_from_request)

Tests the HTTP auth path using FastMCP's StaticTokenVerifier for realistic testing.
"""
import pytest
from unittest.mock import AsyncMock

from app.middleware.auth import get_user_from_request
from app.config.settings import settings


class MockRequest:
    """Mock Starlette Request for testing"""
    def __init__(self, headers: dict | None = None):
        self.headers = headers or {}


class MockFastMCP:
    """Mock FastMCP instance with configurable auth provider"""
    def __init__(self, user_service, auth_provider=None):
        self.user_service = user_service
        self.auth = auth_provider


class MockAccessToken:
    """Mock AccessToken returned by auth provider"""
    def __init__(self, claims: dict):
        self.claims = claims


# ============================================
# Auth Disabled Tests (mcp.auth = None)
# ============================================


@pytest.mark.asyncio
async def test_no_auth_returns_default_user(test_user_service):
    """When mcp.auth is None, returns default user."""
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=None)
    request = MockRequest()

    user = await get_user_from_request(request, mcp)

    assert user is not None
    assert user.external_id == settings.DEFAULT_USER_ID
    assert user.name == settings.DEFAULT_USER_NAME
    assert user.email == settings.DEFAULT_USER_EMAIL


@pytest.mark.asyncio
async def test_no_auth_idempotent(test_user_service):
    """Repeated calls with no auth return same user."""
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=None)
    request = MockRequest()

    user1 = await get_user_from_request(request, mcp)
    user2 = await get_user_from_request(request, mcp)

    assert user1.id == user2.id
    assert user1.external_id == user2.external_id


# ============================================
# Auth Enabled Tests (mcp.auth configured)
# ============================================


@pytest.mark.asyncio
async def test_missing_auth_header_raises(test_user_service):
    """Missing Authorization header raises ValueError."""
    # Create mock auth provider (presence means auth is enabled)
    mock_auth = AsyncMock()
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={})  # No Authorization header

    with pytest.raises(ValueError, match="Missing or invalid Authorization header"):
        await get_user_from_request(request, mcp)


@pytest.mark.asyncio
async def test_invalid_bearer_format_raises(test_user_service):
    """Authorization header without 'Bearer ' prefix raises ValueError."""
    mock_auth = AsyncMock()
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Basic abc123"})

    with pytest.raises(ValueError, match="Missing or invalid Authorization header"):
        await get_user_from_request(request, mcp)


@pytest.mark.asyncio
async def test_invalid_token_raises(test_user_service):
    """Invalid token (verify_token returns None) raises ValueError."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=None)
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer invalid-token"})

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await get_user_from_request(request, mcp)


@pytest.mark.asyncio
async def test_missing_sub_claim_raises(test_user_service):
    """Token without 'sub' claim raises ValueError."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "name": "Test User",
        "email": "test@example.com"
        # Missing 'sub'
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer token-without-sub"})

    with pytest.raises(ValueError, match="Token missing 'sub' claim"):
        await get_user_from_request(request, mcp)


@pytest.mark.asyncio
async def test_valid_token_extracts_all_claims(test_user_service):
    """Valid token with all claims extracts user correctly."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "auth0|user-123",
        "name": "Test User",
        "email": "test@example.com"
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer valid-token"})

    user = await get_user_from_request(request, mcp)

    assert user is not None
    assert user.external_id == "auth0|user-123"
    assert user.name == "Test User"
    assert user.email == "test@example.com"
    mock_auth.verify_token.assert_called_once_with("valid-token")


@pytest.mark.asyncio
async def test_minimal_claims_uses_fallbacks(test_user_service):
    """Token with only 'sub' uses fallback name and email."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "minimal-user-456"
        # No name, email
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer minimal-token"})

    user = await get_user_from_request(request, mcp)

    assert user is not None
    assert user.external_id == "minimal-user-456"
    assert user.name == "User minimal-user-456"  # Fallback
    assert user.email == "minimal-user-456@oauth.local"  # Fallback


@pytest.mark.asyncio
async def test_preferred_username_fallback(test_user_service):
    """Token uses 'preferred_username' when 'name' missing."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "oidc-user-789",
        "preferred_username": "jdoe",
        "email": "jdoe@example.com"
        # No 'name'
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer oidc-token"})

    user = await get_user_from_request(request, mcp)

    assert user.name == "jdoe"  # Falls back to preferred_username


@pytest.mark.asyncio
async def test_login_fallback_github_pattern(test_user_service):
    """Token uses 'login' claim for GitHub pattern."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "12345678",
        "login": "scottrbk",
        "email": "scott@example.com"
        # No 'name' or 'preferred_username'
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer github-token"})

    user = await get_user_from_request(request, mcp)

    assert user.name == "scottrbk"  # Falls back to login


@pytest.mark.asyncio
async def test_auth_idempotent(test_user_service):
    """Repeated calls with same token return same user."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "repeat-user-999",
        "name": "Repeat User",
        "email": "repeat@example.com"
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "Bearer same-token"})

    user1 = await get_user_from_request(request, mcp)
    user2 = await get_user_from_request(request, mcp)

    assert user1.id == user2.id
    assert user1.external_id == user2.external_id


@pytest.mark.asyncio
async def test_lowercase_bearer_accepted(test_user_service):
    """RFC 6750: Bearer scheme is case-insensitive."""
    mock_auth = AsyncMock()
    mock_auth.verify_token = AsyncMock(return_value=MockAccessToken(claims={
        "sub": "case-user-111",
        "name": "Case User",
        "email": "case@example.com"
    }))
    mcp = MockFastMCP(user_service=test_user_service, auth_provider=mock_auth)
    request = MockRequest(headers={"Authorization": "bearer lowercase-token"})

    user = await get_user_from_request(request, mcp)

    assert user is not None
    assert user.external_id == "case-user-111"
    mock_auth.verify_token.assert_called_once_with("lowercase-token")
