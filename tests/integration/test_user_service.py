"""
Integration tests for UserService with stubbed database

Tests critical workflows without real PostgreSQL dependency
"""
import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy.exc import IntegrityError

from app.models.user_models import UserCreate, UserUpdate
from app.services.user_service import UserService


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


# ============================================
# Race condition regression tests
# ============================================


@pytest.mark.asyncio
async def test_get_or_create_user_handles_race_condition(test_user_service):
    """IntegrityError on INSERT falls back to SELECT (concurrent upsert race)"""
    # Pre-create the user so the fallback SELECT succeeds
    user_create = UserCreate(
        external_id="race-user",
        name="Race User",
        email="race@example.com"
    )
    existing = await test_user_service.get_or_create_user(user_create)

    # Now simulate the race: first SELECT returns None, INSERT raises IntegrityError,
    # fallback SELECT returns the existing user
    repo = test_user_service.user_repo
    original_get = repo.get_user_by_external_id
    call_count = 0

    async def get_none_then_real(external_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None  # Simulate SELECT miss (race window)
        return await original_get(external_id)

    async def create_raises(user):
        raise IntegrityError("duplicate key", params=None, orig=Exception())

    with patch.object(repo, "get_user_by_external_id", side_effect=get_none_then_real):
        with patch.object(repo, "create_user", side_effect=create_raises):
            result = await test_user_service.get_or_create_user(user_create)

    assert result is not None
    assert result.id == existing.id
    assert result.external_id == "race-user"


@pytest.mark.asyncio
async def test_update_user_handles_race_condition(test_user_service):
    """IntegrityError on INSERT in update_user falls back to SELECT"""
    # Pre-create the user so the fallback SELECT succeeds
    user_create = UserCreate(
        external_id="race-update-user",
        name="Race Update User",
        email="race-update@example.com"
    )
    existing = await test_user_service.get_or_create_user(user_create)

    user_update = UserUpdate(
        external_id="race-update-user",
        name="Updated Name",
        email="race-update@example.com",
    )

    repo = test_user_service.user_repo
    original_get = repo.get_user_by_external_id
    call_count = 0

    async def get_none_then_real(external_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None
        return await original_get(external_id)

    async def create_raises(user):
        raise IntegrityError("duplicate key", params=None, orig=Exception())

    with patch.object(repo, "get_user_by_external_id", side_effect=get_none_then_real):
        with patch.object(repo, "create_user", side_effect=create_raises):
            result = await test_user_service.update_user(user_update)

    assert result is not None
    assert result.id == existing.id
    assert result.external_id == "race-update-user"
