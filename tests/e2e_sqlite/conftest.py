"""
E2E test fixtures with in-process SQLite (no Docker required)

Spins up FastMCP service with SQLite backend in-memory to validate
end-to-end behavior without Docker orchestration.

Key differences from Docker E2E tests:
- Uses in-memory SQLite database (ephemeral, clean state per run)
- Runs FastMCP server in-process (no HTTP server startup)
- Uses FastMCP test client (no network calls)
- Runs by default (no @pytest.mark.e2e required)
"""
import pytest
from contextlib import asynccontextmanager
from fastmcp import FastMCP

# SQLite repository imports
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.user_repository import SqliteUserRepository
from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
from app.repositories.sqlite.project_repository import SqliteProjectRepository
from app.repositories.sqlite.code_artifact_repository import SqliteCodeArtifactRepository
from app.repositories.sqlite.document_repository import SqliteDocumentRepository
from app.repositories.sqlite.entity_repository import SqliteEntityRepository

# Shared imports
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter, AzureOpenAIAdapter, GoogleEmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import FastEmbedCrossEncoderAdapter
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.services.graph_service import GraphService
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_registry import ToolRegistry
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata
from app.routes.api import health, memories, entities, projects, documents, code_artifacts, graph


@pytest.fixture(scope="module")
def embedding_adapter():
    """
    Module-scoped embedding adapter to avoid reloading model for each test.

    Dynamically selects adapter based on EMBEDDING_PROVIDER setting:
    - Azure: AzureOpenAIAdapter (requires AZURE_* env vars)
    - Google: GoogleEmbeddingsAdapter (requires GOOGLE_AI_API_KEY)
    - Default: FastEmbeddingAdapter (local, zero-config)

    FastEmbed model loading is expensive (~1-2 seconds), so we share the adapter
    across all tests in the module for better performance.
    """
    from app.config.settings import settings

    if settings.EMBEDDING_PROVIDER == "Azure":
        return AzureOpenAIAdapter()
    elif settings.EMBEDDING_PROVIDER == "Google":
        return GoogleEmbeddingsAdapter()
    else:
        return FastEmbeddingAdapter()


@pytest.fixture(scope="module")
def reranker_adapter():
    """
    Module-scoped reranker adapter to avoid reloading model for each test.

    Returns FastEmbedCrossEncoderAdapter if reranking is enabled, None otherwise.
    Cross-encoder model loading is expensive, so we share across tests.
    """
    from app.config.settings import settings

    if settings.RERANKING_ENABLED:
        return FastEmbedCrossEncoderAdapter()
    return None


@pytest.fixture
async def sqlite_app(embedding_adapter, reranker_adapter):
    """
    Create and configure FastMCP application with in-memory SQLite backend

    Function-scoped fixture for test isolation - each test gets a fresh database.

    This fixture:
    - Creates ephemeral in-memory SQLite database
    - Initializes all tables and sqlite-vec extension
    - Sets up all services with SQLite repositories
    - Registers tool metadata in registry
    - Returns configured FastMCP app for testing
    - Cleans up properly after each test
    """
    # Import settings to override for in-memory database
    from app.config.settings import settings

    # Save original settings
    original_sqlite_memory = settings.SQLITE_MEMORY
    original_database = settings.DATABASE

    # Override to use in-memory SQLite database for testing
    settings.DATABASE = "SQLite"
    settings.SQLITE_MEMORY = True

    try:
        # Create database adapter with in-memory SQLite
        db_adapter = SqliteDatabaseAdapter()

        # Initialize database BEFORE creating app (loads sqlite-vec extension)
        await db_adapter.init_db()

        # Create repositories
        user_repository = SqliteUserRepository(db_adapter=db_adapter)
        # Use module-scoped adapters (passed as fixture parameters)
        memory_repository = SqliteMemoryRepository(
            db_adapter=db_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=reranker_adapter,
        )
        project_repository = SqliteProjectRepository(db_adapter=db_adapter)
        code_artifact_repository = SqliteCodeArtifactRepository(db_adapter=db_adapter)
        document_repository = SqliteDocumentRepository(db_adapter=db_adapter)
        entity_repository = SqliteEntityRepository(db_adapter=db_adapter)

        @asynccontextmanager
        async def lifespan(app):
            """Application lifecycle with SQLite initialization"""
            # Database already initialized above

            # Create services after DB is initialized
            user_service = UserService(user_repository)
            memory_service = MemoryService(memory_repository)
            project_service = ProjectService(project_repository)
            code_artifact_service = CodeArtifactService(code_artifact_repository)
            document_service = DocumentService(document_repository)
            entity_service = EntityService(entity_repository)
            graph_service = GraphService(memory_repository, entity_repository)

            # Store services on FastMCP instance for tool access
            mcp.user_service = user_service
            mcp.memory_service = memory_service
            mcp.project_service = project_service
            mcp.code_artifact_service = code_artifact_service
            mcp.document_service = document_service
            mcp.entity_service = entity_service
            mcp.graph_service = graph_service

            # Create and attach registry
            registry = ToolRegistry()
            mcp.registry = registry

            # Register all tools to registry
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

            # Cleanup handled in fixture teardown to avoid event loop closure warnings
            pass

        # Create FastMCP app
        mcp = FastMCP("Forgetful-SQLite-E2E", lifespan=lifespan)

        # Register routes
        health.register(mcp)
        memories.register(mcp)
        entities.register(mcp)
        projects.register(mcp)
        documents.register(mcp)
        code_artifacts.register(mcp)
        graph.register(mcp)
        meta_tools.register(mcp)

        yield mcp

        # Explicit cleanup before event loop closes to prevent warnings
        # Give aiosqlite background threads time to finish
        import asyncio
        await asyncio.sleep(0.1)

        # Dispose of database adapter properly
        try:
            await db_adapter.dispose()
        except (RuntimeError, asyncio.CancelledError):
            # Suppress harmless event loop closure warnings during test teardown
            pass
    finally:
        # Restore original settings
        settings.DATABASE = original_database
        settings.SQLITE_MEMORY = original_sqlite_memory


@pytest.fixture
async def mcp_client(sqlite_app):
    """
    Provide connected MCP client for testing

    This fixture creates a Client connected to the in-process
    FastMCP app via stdio transport. Tests can use this client to call tools directly
    without starting an HTTP server or Docker containers.

    Usage in tests:
        async def test_something(mcp_client):
            result = await mcp_client.call_tool("tool_name", {...})
    """
    from fastmcp import Client

    # Create stdio transport for in-process testing
    async with Client(sqlite_app) as client:
        yield client


@pytest.fixture
async def http_client(sqlite_app):
    """
    Provide HTTP client for testing REST API routes.

    This fixture creates an httpx.AsyncClient connected to the FastMCP app
    via ASGI transport, allowing direct HTTP requests to custom routes
    without starting an HTTP server.

    Usage in tests:
        async def test_api_endpoint(http_client):
            response = await http_client.get("/api/v1/memories")
            assert response.status_code == 200
    """
    from httpx import AsyncClient, ASGITransport
    from fastmcp import Client

    # First, initialize the app by creating MCP client (runs lifespan)
    async with Client(sqlite_app) as _:
        # Create HTTP client using ASGI transport with http_app
        asgi_app = sqlite_app.http_app()
        transport = ASGITransport(app=asgi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
