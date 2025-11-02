"""
Service for user management and auto-provisioning
"""
from uuid import UUID 

from app.models.user_models import User, UserCreate, UserUpdate
from app.protocols.user_protocol import UserRepository
from app.utils.pydantic_helper import get_changed_fields

import logging
logger = logging.getLogger(__name__)

class UserService:
    """
    Handles user auto provisioning and metadata updates for multi-tenant authentication
    """
    
    def __init__(self, user_repo: UserRepository):
       self.user_repo = user_repo 

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Get user by their internal id
        
        Args:
            user_id: Internal user ID
            
        Returns:
            User or None if not found
        """
        return await self.user_repo.get_user_by_id(user_id=user_id)
    
    async def get_or_create_user(self, user: UserCreate) -> User | None:
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
                logger.info("User auto-updated during provisioning",
                            extra={
                                "user_id": str(existing_user.id),
                                "external_id": user.external_id,
                                "changed_fields": list(changed_fields.keys())
                            })
                update_data = UserUpdate(**user.model_dump())
                return await self.user_repo.update_user(
                    user_id=existing_user.id, 
                    updated_user=update_data)
            else:
                return existing_user        
        else: 
            logger.info("Creating user",
                        extra={
                            "external_id": user.external_id,
                            "user_name": user.name})
            new_user = await self.user_repo.create_user(user=user)
            logger.info("User created")
            return new_user
    
    async def update_user(self, user_update: UserUpdate) -> User | None:
        """
            Updates a user record with the updated user details passed to it

            Args:
                user: UserUpdate mode containing the information to update

            Returns:
                User or None
        """
        existing_user = await self.user_repo.get_user_by_external_id(external_id=user_update.external_id)

        if existing_user:
            changed_fields = get_changed_fields(user_update, existing_user)
            if changed_fields:
                logger.info("User auto-updated during provisioning",
                            extra={
                                "user_id": str(existing_user.id),
                                "external_id": existing_user.external_id,
                                "changed_fields": list(changed_fields.keys())
                            })
                return await self.user_repo.update_user(
                    user_id=existing_user.id, 
                    updated_user=user_update)
            else:
                return existing_user        
        else:
            logger.info("User record not found, creating user",
            extra={
                "external_id": user_update.external_id,
                "user_name": user_update.name})
            create_user = UserCreate(**user_update.model_dump())
            logger.info("User created")
            return await self.user_repo.create_user(user=create_user)
        
        

        
