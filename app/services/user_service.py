"""
Service for user management and auto-provisioning
"""
from uuid import UUID 
from typing import Optional

from app.models.user_models import User, UserCreate, UserUpdate
from app.protocols.user_protocol import UserRepository
from app.utils.pydantic_helper import get_changed_fields

class UserService:
    """
    Handles user auto provisioning and metadata updates for multi-tenant authentication
    """
    
    def __init__(self, user_repo: UserRepository):
       self.user_repo = user_repo 

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by their internal id
        
        Args:
            user_id: Internal user ID
            
        Returns:
            User or None if not found
        """
        return await self.user_repo.get_user_by_id(user_id=user_id)
    
    async def get_or_create_user(self, user: UserCreate) -> Optional[User]:
        """Tries to fetch a user based on their external_id and if not exists creates them

        Args:
            user: UserCreate model containing user data for create/update

        Returns:
            User or None
        """
        
        existing_user = await self.user_repo.get_user_by_external_id(external_id=user.external_id)
        
        if existing_user:
            changed_fields = get_changed_fields(user, existing_user)
            if changed_fields:
                #TODO: Log the changed fields
                update_data = UserUpdate(**user.model_dump())
                return await self.user_repo.update_user(
                    user_id=existing_user.id, 
                    updated_user=update_data)
            else:
                return existing_user        
        else: 
            return await self.user_repo.create_user(user=user)
        
    
    async def update_user(self, user_update: UserUpdate) -> Optional[User]:
        """
            Updates a user record with the updated user details passed to it

            Args:
                user: UserUpdate mode containing the information to update

            Returns:
                User or None
        """
        existing_user = await self.user_repo.get_user_by_external_id(external_id=user_update.external_id)
        
        if existing_user:
            changed_fields = get_changed_fields(UserUpdate, existing_user)
            if changed_fields:
                #TODO: Log the changed fields
                update_data = UserUpdate(**user_update.model_dump())
                return await self.user_repo.update_user(
                    user_id=existing_user.id, 
                    updated_user=update_data)
            else:
                return existing_user        
        else: 
            create_user = UserCreate(**user_update.model_dump())
            return await self.user_repo.create_user(user=create_user)
        
        

        
