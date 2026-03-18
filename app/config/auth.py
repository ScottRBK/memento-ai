"""
Auth provider factory for FastMCP v3.

FastMCP v3 removed automatic auth provider construction from environment
variables. This factory reads the same FASTMCP_SERVER_AUTH + FASTMCP_SERVER_AUTH_*
env vars that users already configure and constructs providers explicitly.

Users change nothing — same env vars, same behavior.
"""
import os
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


def _env(key: str, default: str | None = None) -> str | None:
    """Read a FASTMCP_SERVER_AUTH_* env var."""
    return os.getenv(f"FASTMCP_SERVER_AUTH_{key}", default)


def _env_required(key: str) -> str:
    """Read a required FASTMCP_SERVER_AUTH_* env var."""
    value = _env(key)
    if not value:
        raise ValueError(
            f"FASTMCP_SERVER_AUTH_{key} is required when using this auth provider"
        )
    return value


def _env_scopes(key: str) -> list[str] | None:
    """Read a comma-separated scopes env var, returns None if not set."""
    raw = _env(key)
    if not raw:
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


@_register("fastmcp.server.auth.providers.github.GitHubProvider")
def _build_github():
    from fastmcp.server.auth.providers.github import GitHubProvider

    return GitHubProvider(
        client_id=_env_required("GITHUB_CLIENT_ID"),
        client_secret=_env_required("GITHUB_CLIENT_SECRET"),
        base_url=_env_required("GITHUB_BASE_URL"),
        required_scopes=_env_scopes("GITHUB_REQUIRED_SCOPES"),
    )


@_register("fastmcp.server.auth.providers.google.GoogleProvider")
def _build_google():
    from fastmcp.server.auth.providers.google import GoogleProvider

    return GoogleProvider(
        client_id=_env_required("GOOGLE_CLIENT_ID"),
        client_secret=_env_required("GOOGLE_CLIENT_SECRET"),
        base_url=_env_required("GOOGLE_BASE_URL"),
        required_scopes=_env_scopes("GOOGLE_REQUIRED_SCOPES"),
    )


@_register("fastmcp.server.auth.providers.jwt.JWTVerifier")
def _build_jwt():
    from fastmcp.server.auth.providers.jwt import JWTVerifier

    # JWTVerifier needs either jwks_uri or public_key
    jwks_uri = _env("JWT_JWKS_URI")
    public_key = _env("JWT_PUBLIC_KEY")

    if not jwks_uri and not public_key:
        raise ValueError(
            "Either FASTMCP_SERVER_AUTH_JWT_JWKS_URI or "
            "FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY is required for JWTVerifier"
        )

    return JWTVerifier(
        jwks_uri=jwks_uri,
        public_key=public_key,
        issuer=_env("JWT_ISSUER"),
        audience=_env("JWT_AUDIENCE"),
        required_scopes=_env_scopes("JWT_REQUIRED_SCOPES"),
    )


@_register("fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier")
def _build_introspection():
    from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier

    return IntrospectionTokenVerifier(
        introspection_url=_env_required("INTROSPECTION_URL"),
        client_id=_env_required("INTROSPECTION_CLIENT_ID"),
        client_secret=_env_required("INTROSPECTION_CLIENT_SECRET"),
        required_scopes=_env_scopes("INTROSPECTION_REQUIRED_SCOPES"),
        cache_ttl_seconds=settings.TOKEN_CACHE_TTL_SECONDS,
        max_cache_size=settings.TOKEN_CACHE_MAX_SIZE,
    )


def build_auth_provider():
    """
    Build auth provider from FASTMCP_SERVER_AUTH environment variable.

    Returns None when FASTMCP_SERVER_AUTH is not set (no auth mode).
    Raises ValueError for unrecognized provider class paths.
    """
    auth_class_path = os.getenv("FASTMCP_SERVER_AUTH")

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
