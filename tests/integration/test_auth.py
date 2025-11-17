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
@patch('os.getenv')
async def test_get_user_from_auth_default_user(mock_getenv, test_user_service):
    """Test that get_user_from_auth returns default user when AUTH_ENABLED=false"""
    # Mock auth not configured
    mock_getenv.return_value = None

    # Create mock context with test service
    ctx = MockContext(test_user_service)

    # Get user (should auto-create default user)
    user = await auth.get_user_from_auth(ctx)

    assert user is not None
    assert user.external_id == settings.DEFAULT_USER_ID
    assert user.name == settings.DEFAULT_USER_NAME
    assert user.email == settings.DEFAULT_USER_EMAIL


@pytest.mark.asyncio
@patch('os.getenv')
async def test_get_user_from_auth_idempotent(mock_getenv, test_user_service):
    """Test that calling get_user_from_auth multiple times returns same user"""
    # Mock auth not configured
    mock_getenv.return_value = None

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
async def test_auth_enabled_missing_name_generates_fallback(mock_get_token, mock_getenv, test_user_service):
    """Test auth-enabled mode generates fallback name when all name claims missing"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token missing all name claims (name, preferred_username, login)
    mock_token = MockAccessToken(claims={
        "sub": "auth0|test-user-123",
        "email": "test@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Should generate fallback name from sub
    assert user is not None
    assert user.external_id == "auth0|test-user-123"
    assert user.name == "User auth0|test-user-123"
    assert user.email == "test@example.com"


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


# ============================================
# Fallback Handling Tests (Provider-Agnostic)
# ============================================


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_login_fallback(mock_get_token, mock_getenv, test_user_service):
    """Test auth uses 'login' claim when name/preferred_username missing (GitHub pattern)"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.github.GitHubProvider"

    # Mock token with login but no name/preferred_username (GitHub OAuth pattern)
    mock_token = MockAccessToken(claims={
        "sub": "12345678",
        "login": "scottrbk",
        "email": "scott@example.com"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Should use login as name
    assert user is not None
    assert user.external_id == "12345678"
    assert user.name == "scottrbk"
    assert user.email == "scott@example.com"


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_missing_email_generates_placeholder(mock_get_token, mock_getenv, test_user_service):
    """Test auth generates placeholder email when email claim missing"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token missing email claim
    mock_token = MockAccessToken(claims={
        "sub": "oauth2|user-without-email",
        "name": "User Without Email"
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Should generate placeholder email from sub
    assert user is not None
    assert user.external_id == "oauth2|user-without-email"
    assert user.name == "User Without Email"
    assert user.email == "oauth2|user-without-email@oauth.local"


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_null_email_generates_placeholder(mock_get_token, mock_getenv, test_user_service):
    """Test auth handles null email value (OAuth provider returns null instead of omitting)"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.github.GitHubProvider"

    # Mock token with null email (actual bug: GitHub returns {"email": null} when not public)
    mock_token = MockAccessToken(claims={
        "sub": "87654321",
        "login": "ScottRBK",
        "name": None,  # Also null when not set
        "email": None
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Should handle null gracefully with fallbacks
    assert user is not None
    assert user.external_id == "87654321"
    assert user.name == "ScottRBK"  # Falls back to login
    assert user.email == "87654321@oauth.local"  # Generates placeholder


@pytest.mark.asyncio
@patch('os.getenv')
@patch('app.middleware.auth.get_access_token')
async def test_auth_enabled_all_nulls_uses_sub_fallback(mock_get_token, mock_getenv, test_user_service):
    """Test auth handles all name claims null (uses sub-based fallback)"""
    # Mock auth provider configured
    mock_getenv.return_value = "fastmcp.server.auth.providers.jwt.JWTVerifier"

    # Mock token with all possible name claims as null
    mock_token = MockAccessToken(claims={
        "sub": "minimal-oauth-user-999",
        "name": None,
        "preferred_username": None,
        "login": None,
        "email": None
    })
    mock_get_token.return_value = mock_token

    ctx = MockContext(test_user_service)
    user = await auth.get_user_from_auth(ctx)

    # Should use sub-based fallbacks for both name and email
    assert user is not None
    assert user.external_id == "minimal-oauth-user-999"
    assert user.name == "User minimal-oauth-user-999"
    assert user.email == "minimal-oauth-user-999@oauth.local"
