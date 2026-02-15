"""
E2E test fixtures with in-process FastMCP server + session-scoped PostgreSQL

Architecture:
- Session: One PostgreSQL container (docker compose), one db_adapter with migrations
- Module: TRUNCATE tables for isolation, fresh FastMCP app per module
- Function: Fresh MCP client / HTTP client per test

This replaces the previous Docker Compose orchestration (which spun up both
postgres + forgetful-service containers per module) with a much faster approach:
only postgres runs in Docker, the FastMCP server runs in-process.

IMPORTANT: All async fixtures use loop_scope="session" because the asyncpg
connection pool is session-scoped and its connections are bound to the event loop
they were created on. All tests must also run on the session loop.
"""
import asyncio
import subprocess
import time
import typing
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from fastmcp import FastMCP, Client
from httpx import AsyncClient, ASGITransport, AsyncByteStream, Request, Response
from sqlalchemy import text

from app.config.settings import settings
from app.events import EventBus
from app.repositories.embeddings.embedding_adapter import (
    FastEmbeddingAdapter, AzureOpenAIAdapter, GoogleEmbeddingsAdapter,
    OpenAIEmbeddingsAdapter, OllamaEmbeddingsAdapter,
)
from app.repositories.embeddings.reranker_adapter import FastEmbedCrossEncoderAdapter
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.routes.api import health, auth, memories, entities, projects, documents, code_artifacts, graph, activity
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata
from app.routes.mcp.tool_registry import ToolRegistry
from app.services.activity_service import ActivityService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.services.graph_service import GraphService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.user_service import UserService
from main import _create_repositories

# Force all async tests in this directory onto the session event loop.
# Required because asyncpg connections are bound to their creation loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# Streaming ASGI Transport
# ---------------------------------------------------------------------------
# httpx.ASGITransport buffers the entire response body before returning,
# which blocks forever on SSE/streaming endpoints. This transport runs the
# ASGI app as a background task and streams body chunks via an async queue.


class _StreamingBody(AsyncByteStream):
    """Async byte stream backed by an asyncio.Queue, with cleanup."""

    def __init__(self, queue: asyncio.Queue, app_task: asyncio.Task) -> None:
        self._queue = queue
        self._app_task = app_task

    async def __aiter__(self) -> typing.AsyncIterator[bytes]:
        try:
            while True:
                chunk = await self._queue.get()
                if chunk is None:  # sentinel — response complete
                    break
                yield chunk
        finally:
            if not self._app_task.done():
                self._app_task.cancel()
                try:
                    await self._app_task
                except asyncio.CancelledError:
                    pass

    async def aclose(self) -> None:
        if not self._app_task.done():
            self._app_task.cancel()
            try:
                await self._app_task
            except asyncio.CancelledError:
                pass


class StreamingASGITransport(ASGITransport):
    """ASGI transport that properly supports streaming responses (SSE).

    Unlike the base ASGITransport which does ``await self.app(scope, receive, send)``
    (blocking until the entire response body is produced), this transport launches
    the ASGI app as a background task and returns the response as soon as headers
    arrive. Body chunks are yielded incrementally via an async queue.
    """

    async def handle_async_request(self, request: Request) -> Response:
        assert isinstance(request.stream, AsyncByteStream)

        scope: dict[str, typing.Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": request.method,
            "headers": [(k.lower(), v) for (k, v) in request.headers.raw],
            "scheme": request.url.scheme,
            "path": request.url.path,
            "raw_path": request.url.raw_path.split(b"?")[0],
            "query_string": request.url.query or b"",
            "server": (request.url.host, request.url.port),
            "client": self.client if hasattr(self, "client") else ("127.0.0.1", 0),
            "root_path": self.root_path if hasattr(self, "root_path") else "",
        }

        # Request side
        request_body_chunks = request.stream.__aiter__()
        request_complete = False
        disconnect_event = asyncio.Event()

        # Response side
        status_code = None
        response_headers = None
        body_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        headers_event = asyncio.Event()

        async def receive() -> dict[str, typing.Any]:
            nonlocal request_complete
            if request_complete:
                # Block until client disconnects (stream closed / aclose called)
                await disconnect_event.wait()
                return {"type": "http.disconnect"}
            try:
                body = await request_body_chunks.__anext__()
            except StopAsyncIteration:
                request_complete = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.request", "body": body, "more_body": True}

        async def send(message: dict[str, typing.Any]) -> None:
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = message.get("headers", [])
                headers_event.set()
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if body and request.method != "HEAD":
                    await body_queue.put(body)
                if not more_body:
                    await body_queue.put(None)  # sentinel

        # Run the ASGI app in the background
        app_task = asyncio.create_task(self.app(scope, receive, send))

        # Wait for response headers
        await headers_event.wait()

        assert status_code is not None
        assert response_headers is not None

        stream = _StreamingBody(body_queue, app_task)
        return Response(status_code, headers=response_headers, stream=stream)


# All tables to TRUNCATE between modules (order doesn't matter with CASCADE)
ALL_TABLES = [
    "activity_log",
    "memory_links",
    "memory_project_association",
    "memory_code_artifact_association",
    "memory_document_association",
    "memory_entity_association",
    "entity_project_association",
    "entity_relationships",
    "entities",
    "code_artifacts",
    "documents",
    "memories",
    "projects",
    "users",
]


def _wait_for_healthy(container_name: str, timeout: int = 120) -> None:
    """Wait for Docker container to report healthy status."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Health.Status}}", container_name],
                capture_output=True, text=True, check=True
            )
            status = result.stdout.strip()
            if status == "healthy":
                print(f"  {container_name} is healthy")
                return
            if status == "unhealthy":
                raise RuntimeError(f"Container {container_name} is unhealthy")
            time.sleep(1)
        except subprocess.CalledProcessError:
            time.sleep(1)
    raise TimeoutError(f"Container {container_name} did not become healthy within {timeout}s")


def _container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Running}}", container_name],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip() == "true"
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# SESSION-SCOPED FIXTURES (once per entire test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_container():
    """Ensure forgetful-db container is running for the entire test session.

    Starts only the postgres container (not forgetful-service) via docker compose.
    If already running, skips startup.
    """
    project_root = Path(__file__).parent.parent.parent
    compose_file = project_root / "docker" / "docker-compose.yml"
    docker_dir = project_root / "docker"

    # Ensure .env exists (copy from .env.example if missing, e.g. in CI)
    env_file = docker_dir / ".env"
    if not env_file.exists():
        import shutil
        shutil.copy(docker_dir / ".env.example", env_file)
        print("\n  Copied .env.example -> .env")

    if _container_running("forgetful-db"):
        print("\n  forgetful-db already running, reusing")
        _wait_for_healthy("forgetful-db")
    else:
        print("\n  Starting forgetful-db via docker compose...")
        env = {"COMPOSE_PROJECT_NAME": "forgetful"}
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "forgetful-db"],
            env={**dict(__import__("os").environ), **env},
            capture_output=True, text=True, cwd=str(project_root)
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start forgetful-db:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
        _wait_for_healthy("forgetful-db")

    yield

    # Don't tear down — the container is reusable across test runs.
    # Users can `docker compose down -v` manually if needed.


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_adapter(postgres_container):
    """Session-scoped PostgreSQL adapter with Alembic migrations (run once)."""
    original_database = settings.DATABASE
    original_host = settings.POSTGRES_HOST

    settings.DATABASE = "Postgres"
    settings.POSTGRES_HOST = "127.0.0.1"

    adapter = PostgresDatabaseAdapter()
    await adapter.init_db()
    print("  Database migrations complete")

    yield adapter

    await adapter.dispose()
    settings.DATABASE = original_database
    settings.POSTGRES_HOST = original_host


@pytest.fixture(scope="session")
def embedding_adapter():
    """Session-scoped embedding adapter (model loading is expensive ~1-2s)."""
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


@pytest.fixture(scope="session")
def reranker_adapter():
    """Session-scoped reranker adapter (model loading is expensive ~1-2s)."""
    if settings.RERANKING_ENABLED:
        return FastEmbedCrossEncoderAdapter(cache_dir=settings.FASTEMBED_CACHE_DIR)
    return None


# ---------------------------------------------------------------------------
# MODULE-SCOPED FIXTURES (once per test file)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module", loop_scope="session", autouse=True)
async def truncate_tables(db_adapter):
    """Clean all application tables before each module for isolation."""
    table_list = ", ".join(ALL_TABLES)
    async with db_adapter.system_session() as session:
        await session.execute(text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE"))
    print(f"\n  Truncated {len(ALL_TABLES)} tables")


@pytest_asyncio.fixture(scope="module", loop_scope="session")
async def postgres_app(db_adapter, embedding_adapter, reranker_adapter, request):
    """Module-scoped FastMCP app backed by PostgreSQL.

    Reads SETTINGS_OVERRIDE from the test module to apply per-module settings
    (e.g. MEMORY_NUM_AUTO_LINK=0, ACTIVITY_TRACK_READS=True).
    """
    # Apply module-level settings overrides
    overrides = {}
    if hasattr(request, "module") and hasattr(request.module, "SETTINGS_OVERRIDE"):
        overrides = request.module.SETTINGS_OVERRIDE

    saved = {}
    for key, value in overrides.items():
        saved[key] = getattr(settings, key)
        setattr(settings, key, value)

    # Ensure database setting is Postgres for repo creation
    original_database = settings.DATABASE
    original_host = settings.POSTGRES_HOST
    settings.DATABASE = "Postgres"
    settings.POSTGRES_HOST = "127.0.0.1"

    repos = _create_repositories(db_adapter, embedding_adapter, reranker_adapter)

    @asynccontextmanager
    async def lifespan(app):
        """Application lifecycle — creates services, attaches to FastMCP instance."""
        activity_service = ActivityService(repos["activity"])
        event_bus = None

        if settings.ACTIVITY_ENABLED:
            event_bus = EventBus()
            event_bus.subscribe("*.*", activity_service.handle_event)

        user_service = UserService(repos["user"])
        memory_service = MemoryService(repos["memory"], event_bus=event_bus)
        project_service = ProjectService(repos["project"], event_bus=event_bus)
        code_artifact_service = CodeArtifactService(repos["code_artifact"], event_bus=event_bus)
        document_service = DocumentService(repos["document"], event_bus=event_bus)
        entity_service = EntityService(repos["entity"], event_bus=event_bus)
        graph_service = GraphService(
            repos["memory"],
            repos["entity"],
            project_service=project_service,
            document_service=document_service,
            code_artifact_service=code_artifact_service,
        )

        mcp.user_service = user_service
        mcp.memory_service = memory_service
        mcp.project_service = project_service
        mcp.code_artifact_service = code_artifact_service
        mcp.document_service = document_service
        mcp.entity_service = entity_service
        mcp.graph_service = graph_service
        mcp.activity_service = activity_service
        mcp.event_bus = event_bus

        registry = ToolRegistry()
        mcp.registry = registry

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

    mcp = FastMCP("Forgetful-Postgres-E2E", lifespan=lifespan)

    # Register routes
    health.register(mcp)
    auth.register(mcp)
    memories.register(mcp)
    entities.register(mcp)
    projects.register(mcp)
    documents.register(mcp)
    code_artifacts.register(mcp)
    graph.register(mcp)
    activity.register(mcp)
    meta_tools.register(mcp)

    yield mcp

    # Restore settings
    settings.DATABASE = original_database
    settings.POSTGRES_HOST = original_host
    for key, value in saved.items():
        setattr(settings, key, value)


# ---------------------------------------------------------------------------
# FUNCTION-SCOPED FIXTURES (per test)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def mcp_client(postgres_app):
    """Function-scoped MCP client — each test gets a fresh connection.

    In-process transport avoids the SSE timeout/hang issues of Docker transport.
    """
    async with Client(postgres_app) as client:
        yield client


@pytest_asyncio.fixture(loop_scope="session")
async def http_client(postgres_app):
    """Function-scoped HTTP client via streaming ASGI transport for REST API tests.

    Uses StreamingASGITransport instead of httpx.ASGITransport to support
    SSE streaming endpoints (ASGITransport buffers entire response, blocking forever).
    """
    async with Client(postgres_app) as _:
        asgi_app = postgres_app.http_app()
        transport = StreamingASGITransport(app=asgi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


