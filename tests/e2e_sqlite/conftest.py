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
from dataclasses import dataclass, field
from typing import Set
from fastmcp import FastMCP

# SQLite repository imports
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.user_repository import SqliteUserRepository
from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
from app.repositories.sqlite.project_repository import SqliteProjectRepository
from app.repositories.sqlite.code_artifact_repository import SqliteCodeArtifactRepository
from app.repositories.sqlite.document_repository import SqliteDocumentRepository
from app.repositories.sqlite.entity_repository import SqliteEntityRepository
from app.repositories.sqlite.activity_repository import SqliteActivityRepository
from app.repositories.sqlite.plan_repository import SqlitePlanRepository
from app.repositories.sqlite.task_repository import SqliteTaskRepository
from app.repositories.sqlite.file_repository import SqliteFileRepository
from app.repositories.sqlite.skill_repository import SqliteSkillRepository

# Shared imports
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter, AzureOpenAIAdapter, GoogleEmbeddingsAdapter, OpenAIEmbeddingsAdapter, OllamaEmbeddingsAdapter
from app.repositories.embeddings.reranker_adapter import FastEmbedCrossEncoderAdapter, HttpRerankAdapter
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.services.graph_service import GraphService
from app.services.activity_service import ActivityService
from app.services.plan_service import PlanService
from app.services.task_service import TaskService
from app.services.file_service import FileService
from app.services.skill_service import SkillService
from app.events import EventBus
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_registry import ToolRegistry
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata
from app.routes.mcp.scope_resolver import parse_scopes, resolve_permitted_tools
from app.routes.mcp import skill_tools as skills
from app.routes.api import health, auth, memories, entities, projects, documents, code_artifacts, graph, activity, plans, tasks, files
from app.routes.api import skills as skills_api


# ============================================================================
# Feature Flag Registry
# ============================================================================
# Maps feature flag names to the services, tool registry kwargs, and REST route
# modules they control. To add a new feature flag:
#   1. Add an entry here
#   2. Add the wiring logic in _build_feature_services()
#   3. Add route modules to "routes"
# Tests in test_feature_flags_sqlite.py automatically pick up new entries.
# ============================================================================

@dataclass
class FeatureFlagDef:
    """Definition of a feature-flagged capability."""
    # Tool categories that should be absent when disabled
    categories: list[str]
    # Sample tool names to verify absence (not exhaustive — just spot checks)
    sample_tools: list[str]
    # REST route prefixes that should 404 when disabled
    route_prefixes: list[str] = field(default_factory=list)


FEATURE_FLAGS: dict[str, FeatureFlagDef] = {
    "planning": FeatureFlagDef(
        categories=["plan", "task"],
        sample_tools=["create_plan", "create_task", "claim_task", "transition_task"],
        route_prefixes=["/api/v1/plans", "/api/v1/tasks"],
    ),
    "files": FeatureFlagDef(
        categories=["file"],
        sample_tools=["create_file", "get_file", "list_files"],
        route_prefixes=["/api/v1/files"],
    ),
    "skills": FeatureFlagDef(
        categories=["skill"],
        sample_tools=["create_skill", "list_skills", "search_skills"],
        route_prefixes=["/api/v1/skills"],
    ),
}


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
    elif settings.EMBEDDING_PROVIDER == "OpenAI":
        return OpenAIEmbeddingsAdapter()
    elif settings.EMBEDDING_PROVIDER == "Ollama":
        return OllamaEmbeddingsAdapter()
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

    if not settings.RERANKING_ENABLED:
        return None
    if settings.RERANKING_PROVIDER == "HTTP":
        return HttpRerankAdapter()
    else:
        return FastEmbedCrossEncoderAdapter()


# ============================================================================
# App Builder — shared between sqlite_app and feature-flag-off fixtures
# ============================================================================

async def build_sqlite_app(embedding_adapter, reranker_adapter, enabled_features: set[str] | None = None):
    """
    Build a fully-wired FastMCP app with in-memory SQLite.

    Args:
        embedding_adapter: Embedding adapter instance
        reranker_adapter: Reranker adapter instance (or None)
        enabled_features: Set of feature flag names to enable.
            None means ALL features enabled (default for most tests).
            Empty set means no optional features.
    """
    from app.config.settings import settings

    # Save original settings
    original_sqlite_memory = settings.SQLITE_MEMORY
    original_database = settings.DATABASE

    # Override to use in-memory SQLite database for testing
    settings.DATABASE = "SQLite"
    settings.SQLITE_MEMORY = True

    # If None, enable everything
    if enabled_features is None:
        enabled_features = set(FEATURE_FLAGS.keys())

    try:
        # Create database adapter with in-memory SQLite
        db_adapter = SqliteDatabaseAdapter()
        await db_adapter.init_db()

        # Core repositories (always created)
        user_repository = SqliteUserRepository(db_adapter=db_adapter)
        memory_repository = SqliteMemoryRepository(
            db_adapter=db_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=reranker_adapter,
        )
        project_repository = SqliteProjectRepository(db_adapter=db_adapter)
        code_artifact_repository = SqliteCodeArtifactRepository(db_adapter=db_adapter)
        document_repository = SqliteDocumentRepository(db_adapter=db_adapter)
        entity_repository = SqliteEntityRepository(db_adapter=db_adapter)
        activity_repository = SqliteActivityRepository(db_adapter=db_adapter)

        # Feature-flagged repositories
        plan_repository = SqlitePlanRepository(db_adapter=db_adapter) if "planning" in enabled_features else None
        task_repository = SqliteTaskRepository(db_adapter=db_adapter) if "planning" in enabled_features else None
        file_repository = SqliteFileRepository(db_adapter=db_adapter) if "files" in enabled_features else None
        skill_repository = SqliteSkillRepository(
            db_adapter=db_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=reranker_adapter,
        ) if "skills" in enabled_features else None

        @asynccontextmanager
        async def lifespan(app):
            """Application lifecycle with SQLite initialization"""
            event_bus = EventBus()

            activity_service = ActivityService(activity_repository)

            # Core services (always created)
            user_service = UserService(user_repository)
            memory_service = MemoryService(memory_repository, event_bus=None)
            project_service = ProjectService(project_repository, event_bus=None)
            code_artifact_service = CodeArtifactService(code_artifact_repository, event_bus=None)
            document_service = DocumentService(document_repository, event_bus=None)
            entity_service = EntityService(entity_repository, event_bus=None)

            # Feature-flagged services
            plan_service = None
            task_service = None
            file_service = None
            if "planning" in enabled_features:
                plan_service = PlanService(plan_repository, event_bus=None)
                task_service = TaskService(task_repository, plan_service=plan_service, event_bus=None)
            if "files" in enabled_features:
                file_service = FileService(file_repository, event_bus=None)
            skill_service = None
            if "skills" in enabled_features:
                skill_service = SkillService(skill_repository, event_bus=None)

            graph_service = GraphService(
                memory_repository,
                entity_repository,
                project_service=project_service,
                document_service=document_service,
                code_artifact_service=code_artifact_service,
                file_service=file_service,
                skill_service=skill_service,
            )

            # Store core services on FastMCP instance
            mcp.user_service = user_service
            mcp.memory_service = memory_service
            mcp.project_service = project_service
            mcp.code_artifact_service = code_artifact_service
            mcp.document_service = document_service
            mcp.entity_service = entity_service
            mcp.graph_service = graph_service
            mcp.activity_service = activity_service
            mcp.event_bus = event_bus

            # Store feature-flagged services
            if plan_service:
                mcp.plan_service = plan_service
            if task_service:
                mcp.task_service = task_service
            if file_service:
                mcp.file_service = file_service
            if skill_service:
                mcp.skill_service = skill_service

            # Create and attach registry
            registry = ToolRegistry()
            mcp.registry = registry

            # Register tools — optional services passed as None when disabled
            register_all_tools_metadata(
                registry=registry,
                user_service=user_service,
                memory_service=memory_service,
                project_service=project_service,
                code_artifact_service=code_artifact_service,
                document_service=document_service,
                entity_service=entity_service,
                plan_service=plan_service,
                task_service=task_service,
                file_service=file_service,
                skill_service=skill_service,
            )

            # Resolve instance-level scope ceiling
            instance_scopes = parse_scopes(settings.FORGETFUL_SCOPES)
            mcp._instance_permitted_tools = resolve_permitted_tools(instance_scopes, registry)
            mcp._instance_scopes = instance_scopes

            yield

        # Create FastMCP app
        mcp = FastMCP("Forgetful-SQLite-E2E", lifespan=lifespan)

        # Core routes (always registered)
        health.register(mcp)
        auth.register(mcp)
        memories.register(mcp)
        entities.register(mcp)
        projects.register(mcp)
        documents.register(mcp)
        code_artifacts.register(mcp)
        graph.register(mcp)
        activity.register(mcp)

        # Feature-flagged routes
        if "files" in enabled_features:
            files.register(mcp)
        if "planning" in enabled_features:
            plans.register(mcp)
            tasks.register(mcp)
        if "skills" in enabled_features:
            skills.register(mcp)
            skills_api.register(mcp)

        meta_tools.register(mcp)

        yield mcp

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
async def sqlite_app(embedding_adapter, reranker_adapter):
    """
    Create and configure FastMCP application with in-memory SQLite backend.

    All optional features are ENABLED. Function-scoped for test isolation.
    """
    async for app in build_sqlite_app(embedding_adapter, reranker_adapter, enabled_features=None):
        yield app


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


@pytest.fixture(params=[
    pytest.param("*", id="scope-all"),
    pytest.param("read", id="scope-read-only"),
    pytest.param("read:memories", id="scope-read-memories"),
    pytest.param("read,write:memories", id="scope-read-all-write-memories"),
])
async def scoped_mcp_client(request, sqlite_app):
    """
    Parameterized MCP client with different FORGETFUL_SCOPES settings.

    Each parameterization creates a client where the instance-level scopes
    are overridden to test permission enforcement.
    """
    from fastmcp import Client

    scope_string = request.param
    async with Client(sqlite_app) as client:
        # Override instance scopes after lifespan has initialized
        instance_scopes = parse_scopes(scope_string)
        sqlite_app._instance_permitted_tools = resolve_permitted_tools(instance_scopes, sqlite_app.registry)
        sqlite_app._instance_scopes = instance_scopes
        client._scope_string = scope_string  # Stash for test assertions
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
