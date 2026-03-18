"""
Auth provider factory for FastMCP v3.

FastMCP v3 removed automatic auth provider construction from environment
variables. This factory reads the same FASTMCP_SERVER_AUTH + FASTMCP_SERVER_AUTH_*
settings that users already configure and constructs providers explicitly.

All auth settings flow through settings.py for consistency with the rest of
the codebase (supports .env, docker/.env, and platform config .env files).

Users change nothing — same env vars, same behavior.
"""
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Map of recognized provider class paths to their factory functions
_PROVIDER_FACTORIES: dict[str, callable] = {}


def _register(class_path: str):
    """Decorator to register a provider factory for a given class path."""
    def wrapper(fn):
        _PROVIDER_FACTORIES[class_path] = fn
        return fn
    return wrapper


def _required(value: str, field_name: str) -> str:
    """Validate a required setting is not empty."""
    if not value:
        raise ValueError(
            f"{field_name} is required when using this auth provider"
        )
    return value


def _scopes(raw: str) -> list[str] | None:
    """Parse comma-separated scopes string, returns None if empty."""
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


@_register("fastmcp.server.auth.providers.github.GitHubProvider")
def _build_github():
    from fastmcp.server.auth.providers.github import GitHubProvider

    return GitHubProvider(
        client_id=_required(settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID, "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID"),
        client_secret=_required(settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET, "FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET"),
        base_url=_required(settings.FASTMCP_SERVER_AUTH_GITHUB_BASE_URL, "FASTMCP_SERVER_AUTH_GITHUB_BASE_URL"),
        required_scopes=_scopes(settings.FASTMCP_SERVER_AUTH_GITHUB_REQUIRED_SCOPES),
    )


@_register("fastmcp.server.auth.providers.google.GoogleProvider")
def _build_google():
    from fastmcp.server.auth.providers.google import GoogleProvider

    return GoogleProvider(
        client_id=_required(settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID, "FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
        client_secret=_required(settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET, "FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
        base_url=_required(settings.FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL, "FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL"),
        required_scopes=_scopes(settings.FASTMCP_SERVER_AUTH_GOOGLE_REQUIRED_SCOPES),
    )


@_register("fastmcp.server.auth.providers.jwt.JWTVerifier")
def _build_jwt():
    from fastmcp.server.auth.providers.jwt import JWTVerifier

    jwks_uri = settings.FASTMCP_SERVER_AUTH_JWT_JWKS_URI or None
    public_key = settings.FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY or None

    if not jwks_uri and not public_key:
        raise ValueError(
            "Either FASTMCP_SERVER_AUTH_JWT_JWKS_URI or "
            "FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY is required for JWTVerifier"
        )

    return JWTVerifier(
        jwks_uri=jwks_uri,
        public_key=public_key,
        issuer=settings.FASTMCP_SERVER_AUTH_JWT_ISSUER or None,
        audience=settings.FASTMCP_SERVER_AUTH_JWT_AUDIENCE or None,
        required_scopes=_scopes(settings.FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES),
    )


@_register("fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier")
def _build_introspection():
    from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier

    return IntrospectionTokenVerifier(
        introspection_url=_required(settings.FASTMCP_SERVER_AUTH_INTROSPECTION_URL, "FASTMCP_SERVER_AUTH_INTROSPECTION_URL"),
        client_id=_required(settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID, "FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID"),
        client_secret=_required(settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET, "FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET"),
        required_scopes=_scopes(settings.FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES),
        cache_ttl_seconds=settings.TOKEN_CACHE_TTL_SECONDS,
        max_cache_size=settings.TOKEN_CACHE_MAX_SIZE,
    )


def build_auth_provider():
    """
    Build auth provider from FASTMCP_SERVER_AUTH setting.

    Returns None when FASTMCP_SERVER_AUTH is not set (no auth mode).
    Raises ValueError for unrecognized provider class paths.
    """
    auth_class_path = settings.FASTMCP_SERVER_AUTH

    if not auth_class_path:
        logger.info("No auth provider configured (FASTMCP_SERVER_AUTH not set)")
        return None

    factory = _PROVIDER_FACTORIES.get(auth_class_path)
    if factory is None:
        supported = ", ".join(sorted(_PROVIDER_FACTORIES.keys()))
        raise ValueError(
            f"Unrecognized auth provider: {auth_class_path}. "
            f"Supported providers: {supported}"
        )

    provider = factory()
    logger.info(f"Auth provider constructed: {auth_class_path}")
    return provider
