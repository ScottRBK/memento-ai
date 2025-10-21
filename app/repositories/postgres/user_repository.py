"""
User repository for data acess operations
"""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, update

from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.models.user_models import User, UserWrite

class UserRepository:
    """
    Repostiory or User entity operations in Postgres
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
            result = await session.execute(select(User).where(User.id==user_id))
            return result.scalars().first()
        
    async def get_user_by_external_id(self, external_id: str) -> Optional[User]:
        """
        Gets a user by their exteranal id

        Args:
            user_id: external_id string 
        
        Returns:
            User object or None if not found
        """
        async with self.db_adapter.session() as session:
            result = await session.execute(select(User).where(User.external_id==external_id))
            return result.scalars().first()
        

    async def create_user(self, user: UserWrite) -> User:
        """
            Creates a new entry in the user entity 

            Args:
                User: user write object 
            
            Returns
                User object
        """
        async with self.db_adapter.session() as session:
            new_user = User(**user.model_dump)
            session.add(new_user)
            await session.flush()
            await session.refresh(new_user)
            return new_user
        
    async def update_user(self, user_id: UUID, user: User) -> User:
        
    
        