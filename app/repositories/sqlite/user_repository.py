"""
User repository for SQLite data access operations
"""
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound
from datetime import datetime, timezone

from app.repositories.sqlite.sqlite_tables import UsersTable
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.models.user_models import User, UserCreate, UserUpdate
from app.exceptions import NotFoundError

class SqliteUserRepository:
    """
    Repository for User entity operations in SQLite
    """

    def __init__(self, db_adapter: SqliteDatabaseAdapter):
        self.db_adapter = db_adapter


    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """
        Gets a user by their internal id

        Args:
            user_id: Internal User ID (UUID)

        Returns:
            User object or None if not found
        """
        async with self.db_adapter.system_session() as session:
            result = await session.execute(select(UsersTable).where(UsersTable.id == str(user_id)))
            user_orm = result.scalars().first()
            if user_orm:
                return User.model_validate(user_orm)
            return None

    async def get_user_by_external_id(self, external_id: str) -> User | None:
        """
        Gets a user by their external id

        Args:
            user_id: external_id string

        Returns:
            User object or None if not found
        """
        async with self.db_adapter.system_session() as session:
            result = await session.execute(select(UsersTable).where(UsersTable.external_id == external_id))
            user_orm = result.scalars().first()
            if user_orm:
                return User.model_validate(user_orm)
            return None


    async def create_user(self, user: UserCreate) -> User:
        """
            Creates a new entry in the user entity

            Args:
                User Create: user create object

            Returns:
                User object
        """
        async with self.db_adapter.system_session() as session:
            new_user = UsersTable(**user.model_dump())
            session.add(new_user)
            await session.flush()
            await session.refresh(new_user)
            return User.model_validate(new_user)

    async def update_user(self, user_id: UUID, updated_user: UserUpdate) -> User:
        """
            Updates the user entity with the incoming UserUpdate object

            Args:
                user_id: User ID to update
                updated_user: user update object

            Returns:
                User object

            Raises:
                NotFoundError: If user not found
        """
        async with self.db_adapter.system_session() as session:
            update_data = updated_user.model_dump(exclude_unset=True)
            update_data['updated_at'] = datetime.now(timezone.utc)

            stmt = (
                update(UsersTable)
                .where(UsersTable.id == str(user_id))
                .values(**update_data)
                .returning(UsersTable)
            )

            try:
                result = await session.execute(stmt)
                user = result.scalar_one()
                return User.model_validate(user)
            except NoResultFound:
                raise NotFoundError(f"User with id {user_id} not found")



