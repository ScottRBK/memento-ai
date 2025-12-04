"""
Authentication Middleware helpers for integrating with FastMCP and FastAPI
"""
import os
import json
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_access_token, AccessToken
from starlette.requests import Request

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

    # DEBUG: Log all claims to see what we're getting
    logger.debug(f"Token claims received: {json.dumps(claims, indent=2, default=str)}")

    sub = claims.get("sub")
    name = claims.get("name") or claims.get("preferred_username") or claims.get("login") or f"User {sub}"

    if not sub:
        raise ValueError("Token contains no 'sub' claim")

    # Generate placeholder email if not provided by OAuth provider
    email = claims.get("email") or f"{sub}@oauth.local"

    user = UserCreate(
        external_id=sub,
        name=name,
        email=email
    )
    return await user_service.get_or_create_user(user=user)


async def get_user_from_request(request: Request, mcp: FastMCP) -> User:
    """
    Get user for HTTP routes (non-MCP endpoints).

    This is the HTTP equivalent of get_user_from_auth() for MCP tools.
    Used by REST API endpoints that receive Starlette Request instead of FastMCP Context.

    Uses the same auth provider as MCP routes via mcp.auth.verify_token(),
    supporting all FastMCP auth providers (JWT, OAuth2, GitHub, Google, Azure, etc.).

    Args:
        request: Starlette Request object from HTTP route
        mcp: FastMCP instance with attached services

    Returns:
        User: full user model with internal ids and metadata

    Raises:
        ValueError: If auth is enabled but token is missing, invalid, or lacks required claims
    """
    user_service: UserService = mcp.user_service

    # Check if auth is configured via mcp.auth (more reliable than env var)
    if not mcp.auth:
        # No auth configured - use default user
        logger.debug("HTTP auth disabled (mcp.auth not configured) - using default user")
        default_user = UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL
        )
        return await user_service.get_or_create_user(user=default_user)

    # Auth is configured - extract Bearer token from Authorization header
    # RFC 6750: Bearer scheme is case-insensitive
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise ValueError("Missing or invalid Authorization header")

    token = auth_header[7:]  # Strip "Bearer " prefix (length is same regardless of case)

    # Validate token using configured auth provider (works with ANY provider)
    logger.debug(f"Validating Bearer token via {type(mcp.auth).__name__}")
    access_token = await mcp.auth.verify_token(token)

    if access_token is None:
        raise ValueError("Invalid or expired token")

    # Extract claims and provision user (same pattern as MCP auth)
    claims = access_token.claims
    logger.debug(f"Token claims received: {json.dumps(claims, indent=2, default=str)}")

    sub = claims.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub' claim")

    name = claims.get("name") or claims.get("preferred_username") or claims.get("login") or f"User {sub}"
    email = claims.get("email") or f"{sub}@oauth.local"

    user_data = UserCreate(external_id=sub, name=name, email=email)
    return await user_service.get_or_create_user(user=user_data)
