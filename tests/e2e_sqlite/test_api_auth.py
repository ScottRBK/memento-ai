"""
E2E tests for REST API authentication.

Tests that auth-enabled endpoints return proper 401 responses.
Uses StaticTokenVerifier for realistic auth testing.
"""
import pytest
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from httpx import AsyncClient, ASGITransport

# Import from parent conftest setup
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.user_repository import SqliteUserRepository
from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
from app.repositories.sqlite.project_repository import SqliteProjectRepository
from app.repositories.sqlite.code_artifact_repository import SqliteCodeArtifactRepository
from app.repositories.sqlite.document_repository import SqliteDocumentRepository
from app.repositories.sqlite.entity_repository import SqliteEntityRepository
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_registry import ToolRegistry
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata
from app.routes.api import health, memories


# Test tokens for StaticTokenVerifier
# Note: StaticTokenVerifier requires 'client_id' in each token
TEST_TOKENS = {
    "valid-token": {
        "client_id": "test-client",
        "sub": "test-user-123",
        "name": "Test User",
        "email": "test@example.com"
    },
    "minimal-token": {
        "client_id": "test-client",
        "sub": "minimal-user-456"
        # Only required claims (client_id + sub)
    }
}


@pytest.fixture(scope="module")
def auth_embedding_adapter():
    """Module-scoped embedding adapter for auth tests."""
    return FastEmbeddingAdapter()


@pytest.fixture
async def sqlite_app_with_auth(auth_embedding_adapter):
    """
    Create FastMCP app with StaticTokenVerifier auth enabled.

    This allows testing auth-enabled endpoints with controlled test tokens.
    """
    from app.config.settings import settings

    # Save and override settings
    original_sqlite_memory = settings.SQLITE_MEMORY
    original_database = settings.DATABASE
    settings.DATABASE = "SQLite"
    settings.SQLITE_MEMORY = True

    try:
        # Create auth provider with test tokens
        auth_provider = StaticTokenVerifier(tokens=TEST_TOKENS)

        # Create database adapter
        db_adapter = SqliteDatabaseAdapter()
        await db_adapter.init_db()

        # Create repositories
        user_repository = SqliteUserRepository(db_adapter=db_adapter)
        memory_repository = SqliteMemoryRepository(
            db_adapter=db_adapter,
            embedding_adapter=auth_embedding_adapter,
            rerank_adapter=None,
        )
        project_repository = SqliteProjectRepository(db_adapter=db_adapter)
        code_artifact_repository = SqliteCodeArtifactRepository(db_adapter=db_adapter)
        document_repository = SqliteDocumentRepository(db_adapter=db_adapter)
        entity_repository = SqliteEntityRepository(db_adapter=db_adapter)

        @asynccontextmanager
        async def lifespan(app):
            """Application lifecycle with SQLite initialization"""
            # Create services
            user_service = UserService(user_repository)
            memory_service = MemoryService(memory_repository)
            project_service = ProjectService(project_repository)
            code_artifact_service = CodeArtifactService(code_artifact_repository)
            document_service = DocumentService(document_repository)
            entity_service = EntityService(entity_repository)

            # Store services on FastMCP instance
            mcp.user_service = user_service
            mcp.memory_service = memory_service
            mcp.project_service = project_service
            mcp.code_artifact_service = code_artifact_service
            mcp.document_service = document_service
            mcp.entity_service = entity_service

            # Create and attach registry
            registry = ToolRegistry()
            mcp.registry = registry

            # Register all tools
            register_all_tools_metadata(
                registry=registry,
                user_service=user_service,
                memory_service=memory_service,
                project_service=project_service,
                code_artifact_service=code_artifact_service,
                document_service=document_service,
                entity_service=entity_service,
            )

            yield

        # Create FastMCP app WITH auth enabled
        mcp = FastMCP("Forgetful-Auth-E2E", lifespan=lifespan, auth=auth_provider)

        # Register routes
        health.register(mcp)
        memories.register(mcp)
        meta_tools.register(mcp)

        yield mcp

        # Cleanup
        import asyncio
        await asyncio.sleep(0.1)
        try:
            await db_adapter.dispose()
        except (RuntimeError, asyncio.CancelledError):
            pass
    finally:
        settings.DATABASE = original_database
        settings.SQLITE_MEMORY = original_sqlite_memory


@pytest.fixture
async def auth_http_client(sqlite_app_with_auth):
    """
    HTTP client for testing auth-enabled REST API routes.
    """
    from fastmcp import Client

    # Initialize app by creating MCP client (runs lifespan)
    async with Client(sqlite_app_with_auth) as _:
        # Create HTTP client
        asgi_app = sqlite_app_with_auth.http_app()
        transport = ASGITransport(app=asgi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


# ============================================
# Auth-Enabled E2E Tests
# ============================================


class TestAuthEnabled:
    """Test REST API with authentication enabled."""

    @pytest.mark.asyncio
    async def test_no_token_returns_401(self, auth_http_client):
        """Request without Authorization header returns 401."""
        response = await auth_http_client.get("/api/v1/memories")

        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, auth_http_client):
        """Request with invalid token returns 401."""
        response = await auth_http_client.get(
            "/api/v1/memories",
            headers={"Authorization": "Bearer invalid-token-xyz"}
        )

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_valid_token_returns_200(self, auth_http_client):
        """Request with valid token succeeds."""
        response = await auth_http_client.get(
            "/api/v1/memories",
            headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "memories" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_valid_token_creates_memory(self, auth_http_client):
        """Valid token allows creating memories."""
        payload = {
            "title": "Auth Test Memory",
            "content": "Memory created with authenticated request",
            "context": "Testing auth flow",
            "keywords": ["auth", "test"],
            "tags": ["e2e"],
            "importance": 7
        }
        response = await auth_http_client.post(
            "/api/v1/memories",
            json=payload,
            headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Auth Test Memory"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_minimal_token_works(self, auth_http_client):
        """Token with only 'sub' claim works (uses fallbacks)."""
        response = await auth_http_client.get(
            "/api/v1/memories",
            headers={"Authorization": "Bearer minimal-token"}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_wrong_bearer_format_returns_401(self, auth_http_client):
        """Authorization header without 'Bearer ' prefix returns 401."""
        response = await auth_http_client.get(
            "/api/v1/memories",
            headers={"Authorization": "Basic abc123"}
        )

        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["error"]
