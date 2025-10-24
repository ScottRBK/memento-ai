"""
Integration tests for UserService with stubbed database

Tests critical workflows without real PostgreSQL dependency
"""
import pytest
from app.models.user_models import UserCreate, UserUpdate


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new(test_user_service):
    """Test that get_or_create_user auto-provisions a new user"""
    user_create = UserCreate(
        external_id="test-user-1",
        name="Test User",
        email="test@example.com"
    )

    user = await test_user_service.get_or_create_user(user_create)

    assert user is not None
    assert user.external_id == "test-user-1"
    assert user.name == "Test User"
    assert user.email == "test@example.com"
    assert user.id is not None


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(test_user_service):
    """Test that get_or_create_user returns existing user on second call"""
    user_create = UserCreate(
        external_id="test-user-2",
        name="Existing User",
        email="existing@example.com"
    )

    # First call creates
    user1 = await test_user_service.get_or_create_user(user_create)

    # Second call returns existing
    user2 = await test_user_service.get_or_create_user(user_create)

    assert user1.id == user2.id
    assert user1.external_id == user2.external_id


@pytest.mark.asyncio
async def test_update_user_notes(test_user_service):
    """Test updating user notes field"""
    # Create user
    user_create = UserCreate(
        external_id="test-user-3",
        name="Notes User",
        email="notes@example.com"
    )
    user = await test_user_service.get_or_create_user(user_create)

    # Update notes
    user_update = UserUpdate(
        external_id="test-user-3",
        notes="Updated notes content"
    )
    updated_user = await test_user_service.update_user(user_update)

    assert updated_user is not None
    assert updated_user.notes == "Updated notes content"
    assert updated_user.id == user.id


@pytest.mark.asyncio
async def test_user_isolation(test_user_service):
    """Test that different users are properly isolated"""
    user1_create = UserCreate(
        external_id="test-user-4",
        name="User One",
        email="user1@example.com"
    )
    user2_create = UserCreate(
        external_id="test-user-5",
        name="User Two",
        email="user2@example.com"
    )

    user1 = await test_user_service.get_or_create_user(user1_create)
    user2 = await test_user_service.get_or_create_user(user2_create)

    assert user1.id != user2.id
    assert user1.external_id != user2.external_id
    assert user1.email != user2.email
