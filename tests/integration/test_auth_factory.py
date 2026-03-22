"""Integration tests for auth provider factory (app/config/auth.py)

Tests the build_auth_provider() factory and its helpers (_required, _scopes)
that construct FastMCP v3 auth providers from settings.
"""
from unittest.mock import patch

import pytest

from app.config.auth import _required, _scopes, build_auth_provider

# ============================================
# _required() helper tests
# ============================================


def test_required_returns_value_when_present():
    """Valid non-empty string passes through unchanged"""
    assert _required("my-client-id", "CLIENT_ID") == "my-client-id"


def test_required_raises_on_empty_string():
    """Empty string raises ValueError with field name"""
    with pytest.raises(ValueError, match="CLIENT_ID is required"):
        _required("", "CLIENT_ID")


def test_required_raises_on_none():
    """None value raises ValueError"""
    with pytest.raises(ValueError, match="SOME_FIELD is required"):
        _required(None, "SOME_FIELD")


# ============================================
# _scopes() helper tests
# ============================================


def test_scopes_returns_none_for_empty_string():
    """Empty scopes string returns None (no required scopes)"""
    assert _scopes("") is None


def test_scopes_returns_none_for_none():
    """None input returns None"""
    assert _scopes(None) is None


def test_scopes_parses_single_scope():
    """Single scope parsed correctly"""
    assert _scopes("read") == ["read"]


def test_scopes_parses_comma_separated():
    """Comma-separated scopes parsed into list"""
    assert _scopes("read,write,admin") == ["read", "write", "admin"]


def test_scopes_strips_whitespace():
    """Whitespace around scopes is trimmed"""
    assert _scopes(" read , write , admin ") == ["read", "write", "admin"]


def test_scopes_ignores_empty_entries():
    """Empty entries from consecutive commas are filtered out"""
    assert _scopes("read,,write,,,admin") == ["read", "write", "admin"]


def test_scopes_all_empty_returns_empty_list():
    """All-comma string produces empty list (not None — only empty input returns None)"""
    result = _scopes(",,,")
    assert result == []


# ============================================
# build_auth_provider() dispatch tests
# ============================================


@patch("app.config.auth.settings")
def test_build_returns_none_when_not_configured(mock_settings):
    """No auth provider when FASTMCP_SERVER_AUTH is empty"""
    mock_settings.FASTMCP_SERVER_AUTH = ""
    assert build_auth_provider() is None


@patch("app.config.auth.settings")
def test_build_raises_for_unrecognized_provider(mock_settings):
    """Unrecognized class path raises ValueError with supported list"""
    mock_settings.FASTMCP_SERVER_AUTH = "some.fake.Provider"

    with pytest.raises(ValueError, match="Unrecognized auth provider: some.fake.Provider") as exc_info:
        build_auth_provider()

    # Error message should list all supported providers
    assert "github.GitHubProvider" in str(exc_info.value)
    assert "google.GoogleProvider" in str(exc_info.value)
    assert "jwt.JWTVerifier" in str(exc_info.value)
    assert "introspection.IntrospectionTokenVerifier" in str(exc_info.value)


# ============================================
# GitHub provider factory tests
# ============================================


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.github.GitHubProvider")
def test_build_github_provider(MockGitHub, mock_settings):
    """GitHub factory passes correct settings to constructor"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.github.GitHubProvider"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID = "gh-client-id"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET = "gh-secret"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_BASE_URL = "https://github.example.com"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_REQUIRED_SCOPES = "read:user,repo"

    result = build_auth_provider()

    MockGitHub.assert_called_once_with(
        client_id="gh-client-id",
        client_secret="gh-secret",
        base_url="https://github.example.com",
        required_scopes=["read:user", "repo"],
    )
    assert result == MockGitHub.return_value


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.github.GitHubProvider")
def test_build_github_no_scopes(MockGitHub, mock_settings):
    """GitHub factory passes None for empty scopes"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.github.GitHubProvider"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID = "gh-client-id"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET = "gh-secret"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_BASE_URL = "https://github.example.com"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_REQUIRED_SCOPES = ""

    build_auth_provider()

    MockGitHub.assert_called_once_with(
        client_id="gh-client-id",
        client_secret="gh-secret",
        base_url="https://github.example.com",
        required_scopes=None,
    )


@patch("app.config.auth.settings")
def test_build_github_missing_required_field(mock_settings):
    """GitHub factory raises when required field is empty"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.github.GitHubProvider"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID = ""  # Missing!
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_CLIENT_SECRET = "gh-secret"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_BASE_URL = "https://github.example.com"
    mock_settings.FASTMCP_SERVER_AUTH_GITHUB_REQUIRED_SCOPES = ""

    with pytest.raises(ValueError, match="FASTMCP_SERVER_AUTH_GITHUB_CLIENT_ID is required"):
        build_auth_provider()


# ============================================
# Google provider factory tests
# ============================================


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.google.GoogleProvider")
def test_build_google_provider(MockGoogle, mock_settings):
    """Google factory passes correct settings to constructor"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.google.GoogleProvider"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID = "google-client-id"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET = "google-secret"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL = "https://accounts.google.com"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_REQUIRED_SCOPES = "openid,email,profile"

    result = build_auth_provider()

    MockGoogle.assert_called_once_with(
        client_id="google-client-id",
        client_secret="google-secret",
        base_url="https://accounts.google.com",
        required_scopes=["openid", "email", "profile"],
    )
    assert result == MockGoogle.return_value


@patch("app.config.auth.settings")
def test_build_google_missing_required_field(mock_settings):
    """Google factory raises when required field is empty"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.google.GoogleProvider"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID = "google-client-id"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET = ""  # Missing!
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL = "https://accounts.google.com"
    mock_settings.FASTMCP_SERVER_AUTH_GOOGLE_REQUIRED_SCOPES = ""

    with pytest.raises(ValueError, match="FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET is required"):
        build_auth_provider()


# ============================================
# JWT verifier factory tests
# ============================================


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.jwt.JWTVerifier")
def test_build_jwt_with_jwks_uri(MockJWT, mock_settings):
    """JWT factory passes JWKS URI when provided"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.jwt.JWTVerifier"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_JWKS_URI = "https://auth.example.com/.well-known/jwks.json"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY = ""
    mock_settings.FASTMCP_SERVER_AUTH_JWT_ISSUER = "https://auth.example.com"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_AUDIENCE = "my-api"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES = "read,write"

    result = build_auth_provider()

    MockJWT.assert_called_once_with(
        jwks_uri="https://auth.example.com/.well-known/jwks.json",
        public_key=None,
        issuer="https://auth.example.com",
        audience="my-api",
        required_scopes=["read", "write"],
    )
    assert result == MockJWT.return_value


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.jwt.JWTVerifier")
def test_build_jwt_with_public_key(MockJWT, mock_settings):
    """JWT factory passes public key when JWKS URI not provided"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.jwt.JWTVerifier"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_JWKS_URI = ""
    mock_settings.FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\nMIIB..."
    mock_settings.FASTMCP_SERVER_AUTH_JWT_ISSUER = ""
    mock_settings.FASTMCP_SERVER_AUTH_JWT_AUDIENCE = ""
    mock_settings.FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES = ""

    result = build_auth_provider()

    MockJWT.assert_called_once_with(
        jwks_uri=None,
        public_key="-----BEGIN PUBLIC KEY-----\nMIIB...",
        issuer=None,
        audience=None,
        required_scopes=None,
    )
    assert result == MockJWT.return_value


@patch("app.config.auth.settings")
def test_build_jwt_missing_both_key_sources(mock_settings):
    """JWT factory raises when neither JWKS URI nor public key provided"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.jwt.JWTVerifier"
    mock_settings.FASTMCP_SERVER_AUTH_JWT_JWKS_URI = ""
    mock_settings.FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY = ""

    with pytest.raises(ValueError, match="Either FASTMCP_SERVER_AUTH_JWT_JWKS_URI or FASTMCP_SERVER_AUTH_JWT_PUBLIC_KEY is required"):
        build_auth_provider()


# ============================================
# Introspection verifier factory tests
# ============================================


@patch("app.config.auth.settings")
@patch("fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier")
def test_build_introspection_provider(MockIntrospection, mock_settings):
    """Introspection factory passes correct settings including cache params"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_URL = "https://auth.example.com/introspect"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID = "intro-client"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET = "intro-secret"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES = "api:read"
    mock_settings.TOKEN_CACHE_TTL_SECONDS = 600
    mock_settings.TOKEN_CACHE_MAX_SIZE = 2000

    result = build_auth_provider()

    MockIntrospection.assert_called_once_with(
        introspection_url="https://auth.example.com/introspect",
        client_id="intro-client",
        client_secret="intro-secret",
        required_scopes=["api:read"],
        cache_ttl_seconds=600,
        max_cache_size=2000,
    )
    assert result == MockIntrospection.return_value


@patch("app.config.auth.settings")
def test_build_introspection_missing_required_field(mock_settings):
    """Introspection factory raises when required field is empty"""
    mock_settings.FASTMCP_SERVER_AUTH = "fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_URL = "https://auth.example.com/introspect"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID = ""  # Missing!
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET = "intro-secret"
    mock_settings.FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES = ""
    mock_settings.TOKEN_CACHE_TTL_SECONDS = 300
    mock_settings.TOKEN_CACHE_MAX_SIZE = 1000

    with pytest.raises(ValueError, match="FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID is required"):
        build_auth_provider()


# ============================================
# Registry completeness test
# ============================================


def test_all_expected_providers_registered():
    """Verify all four provider class paths are in the factory registry"""
    from app.config.auth import _PROVIDER_FACTORIES

    expected = [
        "fastmcp.server.auth.providers.github.GitHubProvider",
        "fastmcp.server.auth.providers.google.GoogleProvider",
        "fastmcp.server.auth.providers.jwt.JWTVerifier",
        "fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier",
    ]

    for class_path in expected:
        assert class_path in _PROVIDER_FACTORIES, f"Missing factory for {class_path}"

    # No unexpected entries
    assert len(_PROVIDER_FACTORIES) == len(expected)
