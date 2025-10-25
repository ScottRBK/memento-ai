"""
Integration tests for auth module

Tests authentication helpers with stubbed database
"""
import pytest
from app.middleware import auth
from app.config.settings import settings


@pytest.mark.asyncio
async def test_get_user_from_auth_default_user(test_user_service):
    """Test that get_user_from_auth returns default user when AUTH_ENABLED=false"""
    # Initialize auth with test service
    auth.init_auth(test_user_service)

    # Get user (should auto-create default user)
    user = await auth.get_user_from_auth()

    assert user is not None
    assert user.external_id == settings.DEFAULT_USER_ID
    assert user.name == settings.DEFAULT_USER_NAME
    assert user.email == settings.DEFAULT_USER_EMAIL


@pytest.mark.asyncio
async def test_get_user_service_before_init_raises():
    """Test that get_user_service raises error if not initialized"""
    # Reset the global service
    auth._user_service = None

    with pytest.raises(RuntimeError, match="User Service not initialised"):
        auth.get_user_service()
