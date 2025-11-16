"""
Authentication Middleware helpers for integrating with FastMCP and FastAPI
"""
import os
from fastmcp import Context
from fastmcp.server.dependencies import get_access_token, AccessToken

from app.services.user_service import UserService
from app.models.user_models import User, UserCreate
from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)


async def get_user_from_auth(ctx: Context) -> User:
    """
    Provides user context for MCP and API interaction.

    FastMCP handles authentication via environment variables. This function detects
    the auth mode and provisions users accordingly:
    - When FASTMCP_SERVER_AUTH is not set: Uses default user (no auth)
    - When FASTMCP_SERVER_AUTH is set: Extracts user from validated access token

    See: https://fastmcp.wiki/en/servers/auth/authentication

    Args:
        ctx: FastMCP Context object (automatically injected by FastMCP)

    Returns:
        User: full user model with internal ids and meta data plus external ids, name, email, idp_metadata and notes
    """
    # Access user service via context pattern
    user_service: UserService = ctx.fastmcp.user_service

    # Check if FastMCP auth is configured via environment variable
    auth_provider = os.getenv("FASTMCP_SERVER_AUTH")

    if not auth_provider:
        # No auth configured - use default user
        logger.info("Authentication disabled (FASTMCP_SERVER_AUTH not set) - using default user")
        default_user = UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL
        )
        return await user_service.get_or_create_user(user=default_user)

    # Auth is configured - extract user from validated token
    logger.info(f"Authentication enabled ({auth_provider}) - extracting user from token")
    token: AccessToken | None = get_access_token()

    if token is None:
        raise ValueError("Authentication required but no bearer token provided")

    claims = token.claims

    sub = claims.get("sub")
    name = claims.get("name") or claims.get("preferred_username")

    if not sub:
        raise ValueError("Token contains no 'sub' claim")

    if not name:
        raise ValueError("Token requires 'name' or 'preferred_username' claim")

    user = UserCreate(
        external_id=sub,
        name=name,
        email=claims.get("email", "")
    )
    return await user_service.get_or_create_user(user=user)
