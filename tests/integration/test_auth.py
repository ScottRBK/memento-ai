"""
Integration tests for auth module

Tests authentication helpers with stubbed database and context pattern
"""
import pytest
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
