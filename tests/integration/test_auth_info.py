"""
Integration tests for /api/v1/auth/info endpoint

Tests auth mode detection logic with mocked FastMCP instances.
"""
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from fastmcp.server.auth.auth import OAuthProvider, TokenVerifier

from app.routes.api.auth import register, OAUTH_PROVIDER_MAP


class MockFastMCP:
    """Mock FastMCP instance for testing auth detection"""

    def __init__(self, auth_provider=None):
        self.auth = auth_provider
        self._routes = []

    def custom_route(self, path: str, methods: list[str] = None):
        """Decorator that captures route handlers"""
        def decorator(func):
            self._routes.append((path, methods or ["GET"], func))
            return func
        return decorator


def create_test_app(mcp: MockFastMCP) -> Starlette:
    """Create a Starlette app from the mocked FastMCP routes"""
    routes = []
    for path, methods, handler in mcp._routes:
        routes.append(Route(path, handler, methods=methods))
    return Starlette(routes=routes)


# Create fake provider classes for testing type(provider).__name__ detection


class GitHubProvider(OAuthProvider):
    """Fake GitHub provider for testing"""
    def __init__(self):
        pass  # Skip parent init


class GoogleProvider(OAuthProvider):
    """Fake Google provider for testing"""
    def __init__(self):
        pass


class CustomOAuthProvider(OAuthProvider):
    """Unknown OAuth provider for testing"""
    def __init__(self):
        pass


class JWTVerifier(TokenVerifier):
    """Fake JWT verifier for testing"""
    def __init__(self):
        pass


class StaticTokenVerifier(TokenVerifier):
    """Fake static token verifier for testing"""
    def __init__(self):
        pass


class IntrospectionProvider:
    """Fake introspection provider for testing"""
    pass


# ============================================
# Auth Disabled Tests
# ============================================


def test_auth_disabled_returns_correct_response():
    """When mcp.auth is None, returns authEnabled=false, authMode='disabled'"""
    mcp = MockFastMCP(auth_provider=None)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is False
    assert data["authMode"] == "disabled"
    assert data["oauthProviders"] == []
    assert data["loginUrl"] is None


# ============================================
# OAuth Provider Tests
# ============================================


def test_github_oauth_provider():
    """GitHub OAuth provider returns correct oauth mode and provider"""
    mock_auth = GitHubProvider()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "oauth"
    assert data["oauthProviders"] == ["github"]
    assert data["loginUrl"] == "/authorize"


def test_google_oauth_provider():
    """Google OAuth provider returns correct oauth mode and provider"""
    mock_auth = GoogleProvider()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "oauth"
    assert data["oauthProviders"] == ["google"]
    assert data["loginUrl"] == "/authorize"


def test_unknown_oauth_provider():
    """Unknown OAuth provider returns 'unknown' identifier"""
    mock_auth = CustomOAuthProvider()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "oauth"
    assert data["oauthProviders"] == ["unknown"]
    assert data["loginUrl"] == "/authorize"


# ============================================
# JWT Provider Tests
# ============================================


def test_jwt_verifier_provider():
    """JWT verifier returns jwt mode"""
    mock_auth = JWTVerifier()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "jwt"
    assert data["oauthProviders"] == []
    assert data["loginUrl"] is None


def test_static_token_verifier():
    """StaticTokenVerifier returns jwt mode"""
    mock_auth = StaticTokenVerifier()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "jwt"
    assert data["oauthProviders"] == []
    assert data["loginUrl"] is None


# ============================================
# Introspection Provider Tests
# ============================================


def test_introspection_provider():
    """Introspection provider returns introspection mode"""
    mock_auth = IntrospectionProvider()

    mcp = MockFastMCP(auth_provider=mock_auth)
    register(mcp)

    app = create_test_app(mcp)
    client = TestClient(app)

    response = client.get("/api/v1/auth/info")

    assert response.status_code == 200
    data = response.json()
    assert data["authEnabled"] is True
    assert data["authMode"] == "introspection"
    assert data["oauthProviders"] == []
    assert data["loginUrl"] is None


# ============================================
# Provider Map Coverage Tests
# ============================================


def test_all_oauth_providers_mapped():
    """Verify all expected OAuth providers are in the mapping"""
    expected_providers = [
        "GitHubProvider",
        "GoogleProvider",
        "AzureProvider",
        "Auth0Provider",
        "DiscordProvider",
        "SupabaseProvider",
        "WorkOSProvider",
        "DescopeProvider",
        "ScalekitProvider",
        "OCIProvider",
        "AWSProvider",
        "AWSCognitoProvider",
    ]

    for provider in expected_providers:
        assert provider in OAUTH_PROVIDER_MAP, f"Missing mapping for {provider}"


def test_provider_map_values_are_lowercase():
    """All OAuth provider identifiers should be lowercase"""
    for provider_class, oauth_id in OAUTH_PROVIDER_MAP.items():
        assert oauth_id == oauth_id.lower(), f"{provider_class} has non-lowercase id: {oauth_id}"
