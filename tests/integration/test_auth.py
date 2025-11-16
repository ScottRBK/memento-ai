"""
Integration tests for auth module

Tests authentication helpers with stubbed database and context pattern
"""
import pytest
from unittest.mock import patch
from app.middleware import auth
from app.config.settings import settings


class MockFastMCP:
    """Mock FastMCP instance for testing context pattern"""
    def __init__(self, user_service):
        self.user_service = user_service


class MockContext:
    """Mock Context object for testing"""
    def __init__(self, user_service):
        self.fastmcp = MockFastMCP(user_service)


class MockAccessToken:
    """Mock AccessToken for testing auth-enabled mode"""
    def __init__(self, claims: dict):
        self.claims = claims


@pytest.mark.asyncio
async def test_get_user_from_auth_default_user(test_user_service):
    """Test that get_user_from_auth returns default user when AUTH_ENABLED=false"""
    # Create mock context with test service
    ctx = MockContext(test_user_service)

    # Get user (should auto-create default user)
    user = await auth.get_user_from_auth(ctx)

    assert user is not None
    assert user.external_id == settings.DEFAULT_USER_ID
    assert user.name == settings.DEFAULT_USER_NAME
    assert user.email == settings.DEFAULT_USER_EMAIL


@pytest.mark.asyncio
async def test_get_user_from_auth_idempotent(test_user_service):
    """Test that calling get_user_from_auth multiple times returns same user"""
    ctx = MockContext(test_user_service)

    # Call twice
    user1 = await auth.get_user_from_auth(ctx)
    user2 = await auth.get_user_from_auth(ctx)

    # Should be same user (same ID)
    assert user1.id == user2.id
    assert user1.external_id == user2.external_id


# ============================================
# Auth-Enabled Mode Tests (with mocked tokens)
# ============================================


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_with_valid_token(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode with valid bearer token"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock valid access token with all required claims
    mock_token = MockAccessToken(claims={
        "sub": "auth0|test-user-123",
        "name": "Test User",
        "email": "test@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Verify user provisioned from token claims
    assert user is not None
    assert user.external_id == "auth0|test-user-123"
    assert user.name == "Test User"
    assert user.email == "test@example.com"


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_missing_token(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode fails when no bearer token provided"""
    # Mock auth provider configured (auth required)
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock no token provided
    mock_get_token.return_value = None

    ctx = MockContext(test_user_service)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Authentication required but no bearer token provided"):
        await auth.get_user_from_auth(ctx)


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_missing_sub_claim(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode fails when token missing 'sub' claim"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token missing 'sub' claim
    mock_token = MockAccessToken(claims={
        "name": "Test User",
        "email": "test@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Token contains no 'sub' claim"):
        await auth.get_user_from_auth(ctx)


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_missing_name_claims(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode fails when token missing both 'name' and 'preferred_username' claims"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token missing both name claims
    mock_token = MockAccessToken(claims={
        "sub": "auth0|test-user-123",
        "email": "test@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)

    # Should raise ValueError
    with pytest.raises(ValueError, match="Token requires 'name' or 'preferred_username' claim"):
        await auth.get_user_from_auth(ctx)


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_preferred_username_fallback(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode uses 'preferred_username' when 'name' missing"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token with preferred_username but no name
    mock_token = MockAccessToken(claims={
        "sub": "auth0|test-user-456",
        "preferred_username": "testuser456",
        "email": "testuser456@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Verify user created with preferred_username as name
    assert user is not None
    assert user.external_id == "auth0|test-user-456"
    assert user.name == "testuser456"
    assert user.email == "testuser456@example.com"


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_idempotency(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode returns same user for repeated calls with same token"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock same token for both calls
    mock_token = MockAccessToken(claims={
        "sub": "auth0|test-user-789",
        "name": "Repeat User",
        "email": "repeat@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)

    # Call twice with same token
    user1 = await auth.get_user_from_auth(ctx)
    user2 = await auth.get_user_from_auth(ctx)

    # Should be same user (not duplicate)
    assert user1.id == user2.id
    assert user1.external_id == user2.external_id
    assert user1.external_id == "auth0|test-user-789"
