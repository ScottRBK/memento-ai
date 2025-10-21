"""
User repository for data acess operations
"""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, update
from datetime import datetime, timezone

from app.repositories.postgres.postgres_tables import UsersTable
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.models.user_models import User, UserCreate, UserUpdate

class UserRepository:
    """
    Repository or User entity operations in Postgres
    """
    
    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        self.db_adapter = db_adapter
    
    
    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Gets a user by their internal id

        Args:
            user_id: Internal User ID (UUID)
        
        Returns:
            User object or None if not found
        """
        async with self.db_adapter.session() as session:
            result = await session.execute(select(UsersTable).where(UsersTable.id==user_id))
            user_orm = result.scalars().first()
            if user_orm:
                return User.model_validate(user_orm)
            return None 

    async def get_user_by_external_id(self, external_id: str) -> Optional[User]:
        """
        Gets a user by their external id

        Args:
            user_id: external_id string 
        
        Returns:
            User object or None if not found
        """
        async with self.db_adapter.session() as session:
            result = await session.execute(select(UsersTable).where(UsersTable.external_id==external_id))
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
        async with self.db_adapter.session() as session:
            new_user = UsersTable(**user.model_dump())
            session.add(new_user)
            await session.flush()
            await session.refresh(new_user)
            return User.model_validate(new_user) 
        
    async def update_user(self, user_id: UUID, updated_user: UserUpdate) -> User:
        """
            Updates the user entity with the incoming UserCreate object

            Args:
                User Update: user update object

            Returns:
                User object
        """
        async with self.db_adapter.session() as session:
            update_data = updated_user.model_dump(exclude_unset=True)
            update_data['updated_at'] = datetime.now(timezone.utc)
            
            stmt = (
                update(UsersTable)
                .where(UsersTable.id == user_id)
                .values(**update_data)
                .returning(UsersTable)
            )
            
            result = await session.execute(stmt)
            user = result.scalar_one()
            
            return User.model_validate(user)
            
    
        