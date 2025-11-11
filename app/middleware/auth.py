"""
Authentication Middleware helpers for integrating with FastMCP and FastAPI
"""
from fastmcp import Context

from app.services.user_service import UserService
from app.models.user_models import User, UserCreate
from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)


async def get_user_from_auth(ctx: Context) -> User:
    """
    Provides user context for MCP and API interaction.

    Works with FastMCP and FastAPIs authentication approach
    - When AUTH_ENABLED=true in the environments file then this will validate the token
    and provision the user
    - When AUTH_ENABLED=false then it will use a default user profile

    Args:
        ctx: FastMCP Context object (automatically injected by FastMCP)

    Returns:
        User: full user model with internal ids and meta data plus external ids, name, email, idp_metadata and notes
    """
    # Access user service via context pattern
    user_service: UserService = ctx.fastmcp.user_service

    if not settings.AUTH_ENABLED:
        logger.info("Authentication disabled - using default user")
        default_user = UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL
        )
        return await user_service.get_or_create_user(user=default_user)

    #TODO: Implement Token validaiton and provisioning
    logger.warning("Token authentication not yet implemented")