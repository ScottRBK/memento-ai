"""
Authentication Middleware helpers for integrating with FastMCP and FastAPI
"""
import os
import json
import hashlib
import time
from asyncio import Lock
from collections import OrderedDict
from dataclasses import dataclass

from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_access_token, AccessToken
from starlette.requests import Request

from app.services.user_service import UserService
from app.models.user_models import User, UserCreate
from app.config.settings import settings

import logging
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached token validation result."""
    user: User
    expires_at: float


class TokenCache:
    """
    LRU cache for validated OAuth tokens with TTL expiration.

    Security considerations:
    - Stores SHA-256 hash of tokens, never raw tokens
    - Caches User objects only, not sensitive token data
    - TTL prevents stale sessions
    - Size limit prevents memory exhaustion
    """

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def _hash_token(self, token: str) -> str:
        """Hash token for secure cache key."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def get(self, token: str) -> User | None:
        """Get cached user for token, or None if not cached/expired."""
        key = self._hash_token(token)
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            if time.time() >= entry.expires_at:
                # Expired - remove and return None
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (LRU)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.user

    async def set(self, token: str, user: User) -> None:
        """Cache user for token."""
        key = self._hash_token(token)
        expires_at = time.time() + self._ttl

        async with self._lock:
            # Evict oldest if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(user=user, expires_at=expires_at)

    async def invalidate(self, token: str) -> None:
        """Remove token from cache (for logout/revocation)."""
        key = self._hash_token(token)
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    @property
    def stats(self) -> dict:
        """Return cache statistics for monitoring."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "hit_rate": self._hits / total if total > 0 else 0
        }


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
    user_service: UserService = ctx.fastmcp.user_service

    auth_provider = os.getenv("FASTMCP_SERVER_AUTH")

    if not auth_provider:
        logger.info("Authentication disabled (FASTMCP_SERVER_AUTH not set) - using default user")
        default_user = UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL
        )
        return await user_service.get_or_create_user(user=default_user)

    logger.info(f"Authentication enabled ({auth_provider}) - extracting user from token")
    token: AccessToken | None = get_access_token()

    if token is None:
        raise ValueError("Authentication required but no bearer token provided")

    claims = token.claims

    logger.debug(f"Token claims received: {json.dumps(claims, indent=2, default=str)}")

    sub = claims.get("sub")
    name = claims.get("name") or claims.get("preferred_username") or claims.get("login") or f"User {sub}"

    if not sub:
        raise ValueError("Token contains no 'sub' claim")

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

    Uses token caching to avoid expensive upstream validation on every request.
    Cache behavior controlled by TOKEN_CACHE_* settings.

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
        # No auth configured - use default user (no caching needed)
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

    # Check cache first (if enabled and cache exists)
    cache: TokenCache | None = getattr(mcp, 'token_cache', None)
    if cache and settings.TOKEN_CACHE_ENABLED:
        cached_user = await cache.get(token)
        if cached_user:
            logger.debug("Token cache HIT - returning cached user")
            return cached_user
        logger.debug("Token cache MISS - validating token")

    # Cache miss or disabled - validate token via provider
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
    user = await user_service.get_or_create_user(user=user_data)

    # Cache the validated user
    if cache and settings.TOKEN_CACHE_ENABLED:
        await cache.set(token, user)
        logger.debug(f"Token cached (TTL: {settings.TOKEN_CACHE_TTL_SECONDS}s)")

    return user
