"""
Integration test fixtures with in-memory stubs (no real database required)
"""
import pytest
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.models.user_models import User, UserCreate, UserUpdate
from app.protocols.user_protocol import UserRepository
from app.services.user_service import UserService


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of UserRepository for testing"""

    def __init__(self):
        self._users: dict[UUID, User] = {}
        self._external_id_index: dict[str, UUID] = {}

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        return self._users.get(user_id)

    async def get_user_by_external_id(self, external_id: str) -> Optional[User]:
        user_id = self._external_id_index.get(external_id)
        if user_id:
            return self._users.get(user_id)
        return None

    async def create_user(self, user: UserCreate) -> User:
        user_id = uuid4()
        now = datetime.now(timezone.utc)

        new_user = User(
            id=user_id,
            external_id=user.external_id,
            name=user.name,
            email=user.email,
            notes=user.notes,
            idp_metadata=user.idp_metadata,
            created_at=now,
            updated_at=now
        )

        self._users[user_id] = new_user
        self._external_id_index[user.external_id] = user_id
        return new_user

    async def update_user(self, user_id: UUID, updated_user: UserUpdate) -> Optional[User]:
        user = self._users.get(user_id)
        if not user:
            return None

        # Update fields
        update_data = updated_user.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field != "external_id":  # Don't update external_id
                setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)
        return user


@pytest.fixture
def clean_test_data():
    """Fixture that provides a clean slate for each test"""
    # Setup: nothing needed
    yield
    # Teardown: nothing needed (new instance per test)


@pytest.fixture
def mock_user_repository():
    """Provides an in-memory user repository"""
    return InMemoryUserRepository()


@pytest.fixture
def test_user_service(mock_user_repository):
    """Provides a UserService with in-memory repository"""
    return UserService(mock_user_repository)
