"""
Authentication Middleware helpers for integrating with FastMCP
"""
from typing import Optional
from app.services.user_service import UserService
from app.models.user_models import User, UserCreate
from app.config.settings import settings
_user_service: Optional[UserService]

def init_mcp_auth(user_service: UserService):
    """Initiates MCP auth with UserService Instance"""
    global _user_service
    _user_service = user_service

async def get_mcp_user() -> User:
    """
    Provides user context for MCP interaction. 

    Works with FastMCP's authentication system:
    - When AUTH_ENABLED=true in the environments file then this will validate the token
    and provision the user
    - When AUTH_ENABLED=false then it will use a default user profile
    
    Returns:
        User: full user model with internal ids and meta data plus external ids, name, email, idp_metadata and notes
    """

    if not settings.AUTH_ENABLED:
        default_user = UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL
        )
        return await _user_service.get_or_create_user(user=default_user)
    
    #TODO: Implement Token validaiton and provisioning