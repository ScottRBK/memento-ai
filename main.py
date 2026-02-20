"""
    FastAPI application for a python service
"""
import argparse
import asyncio
import signal
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config.settings import settings
from app.version import get_version
from app.routes.api import health, memories, entities, projects, documents, code_artifacts, graph, auth, activity
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_registry import ToolRegistry
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata

# NOTE: Logging is configured inside lifespan() to avoid STDIO pollution
# before MCP handshake completes. Do NOT add module-level logging here.
import logging
import atexit

# Global references - initialized in lifespan()
_queue_listener = None
logger = logging.getLogger(__name__)


def _get_embedding_adapter():
    """Create embedding adapter based on settings. Called during lifespan."""
    from app.repositories.embeddings.embedding_adapter import (
        FastEmbeddingAdapter, AzureOpenAIAdapter, GoogleEmbeddingsAdapter,
        OpenAIEmbeddingsAdapter, OllamaEmbeddingsAdapter,
    )

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


def _get_reranker_adapter():
    """Create reranker adapter if enabled. Called during lifespan."""
    if settings.RERANKING_ENABLED:
        from app.repositories.embeddings.reranker_adapter import FastEmbedCrossEncoderAdapter
        return FastEmbedCrossEncoderAdapter(
            cache_dir=settings.FASTEMBED_CACHE_DIR
        )
    return None


def _check_first_run_models():
    """Log message on first run when models need to be downloaded."""
    cache_dir = Path(settings.FASTEMBED_CACHE_DIR)
    if not cache_dir.exists() or not any(cache_dir.iterdir()):
        logger.info("First run detected - downloading embedding models. This may take a minute...")


def _create_repositories(db_adapter, embeddings_adapter, reranker_adapter):
    """Create all repositories based on database setting. Called during lifespan."""
    if settings.DATABASE == "Postgres":
        from app.repositories.postgres.user_repository import PostgresUserRepository
        from app.repositories.postgres.memory_repository import PostgresMemoryRepository
        from app.repositories.postgres.project_repository import PostgresProjectRepository
        from app.repositories.postgres.code_artifact_repository import PostgresCodeArtifactRepository
        from app.repositories.postgres.document_repository import PostgresDocumentRepository
        from app.repositories.postgres.entity_repository import PostgresEntityRepository
        from app.repositories.postgres.activity_repository import PostgresActivityRepository

        return {
            "user": PostgresUserRepository(db_adapter=db_adapter),
            "memory": PostgresMemoryRepository(
                db_adapter=db_adapter,
                embedding_adapter=embeddings_adapter,
                rerank_adapter=reranker_adapter,
            ),
            "project": PostgresProjectRepository(db_adapter=db_adapter),
            "code_artifact": PostgresCodeArtifactRepository(db_adapter=db_adapter),
            "document": PostgresDocumentRepository(db_adapter=db_adapter),
            "entity": PostgresEntityRepository(db_adapter=db_adapter),
            "activity": PostgresActivityRepository(db_adapter=db_adapter),
        }
    elif settings.DATABASE == "SQLite":
        from app.repositories.sqlite.user_repository import SqliteUserRepository
        from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
        from app.repositories.sqlite.project_repository import SqliteProjectRepository
        from app.repositories.sqlite.code_artifact_repository import SqliteCodeArtifactRepository
        from app.repositories.sqlite.document_repository import SqliteDocumentRepository
        from app.repositories.sqlite.entity_repository import SqliteEntityRepository
        from app.repositories.sqlite.activity_repository import SqliteActivityRepository

        return {
            "user": SqliteUserRepository(db_adapter=db_adapter),
            "memory": SqliteMemoryRepository(
                db_adapter=db_adapter,
                embedding_adapter=embeddings_adapter,
                rerank_adapter=reranker_adapter,
            ),
            "project": SqliteProjectRepository(db_adapter=db_adapter),
            "code_artifact": SqliteCodeArtifactRepository(db_adapter=db_adapter),
            "document": SqliteDocumentRepository(db_adapter=db_adapter),
            "entity": SqliteEntityRepository(db_adapter=db_adapter),
            "activity": SqliteActivityRepository(db_adapter=db_adapter),
        }
    else:
        raise ValueError(f"Unsupported DATABASE setting: {settings.DATABASE}. Must be 'Postgres' or 'SQLite'")


def _create_db_adapter():
    """Create database adapter based on settings. Called during lifespan."""
    if settings.DATABASE == "Postgres":
        from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
        return PostgresDatabaseAdapter()
    elif settings.DATABASE == "SQLite":
        from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
        return SqliteDatabaseAdapter()
    else:
        raise ValueError(f"Unsupported DATABASE setting: {settings.DATABASE}. Must be 'Postgres' or 'SQLite'")


@asynccontextmanager
async def lifespan(app):
    """Manages application lifecycle.
    """
    global _queue_listener

    from app.config.logging_config import configure_logging, shutdown_logging
    _queue_listener = configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT
    )
    atexit.register(shutdown_logging)

    logger.info("Starting session", extra={"service": settings.SERVICE_NAME})

    _check_first_run_models()

    embeddings_adapter = _get_embedding_adapter()
    reranker_adapter = _get_reranker_adapter()
    logger.info("Embedding adapters initialized")

    db_adapter = _create_db_adapter()

    if settings.DATABASE == "SQLite" and not settings.SQLITE_MEMORY:
        data_dir = Path(settings.SQLITE_PATH).parent
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data directory ensured: {data_dir}")

    await db_adapter.init_db()
    logger.info("Database initialized")

    repos = _create_repositories(db_adapter, embeddings_adapter, reranker_adapter)

    from app.services.user_service import UserService
    from app.services.memory_service import MemoryService
    from app.services.project_service import ProjectService
    from app.services.code_artifact_service import CodeArtifactService
    from app.services.document_service import DocumentService
    from app.services.entity_service import EntityService
    from app.services.graph_service import GraphService
    from app.services.activity_service import ActivityService
    from app.events import EventBus

    # Create activity service (always available for API queries)
    # Event bus only created when activity tracking is enabled
    activity_service = ActivityService(repos["activity"])
    event_bus = None

    if settings.ACTIVITY_ENABLED:
        event_bus = EventBus()
        event_bus.subscribe("*.*", activity_service.handle_event)
        logger.info("Activity tracking enabled - event bus initialized")
    else:
        logger.info("Activity tracking disabled (ACTIVITY_ENABLED=false) - API available but no events emitted")

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
    logger.info("Services initialized and attached to FastMCP instance")

    # Initialize token cache for HTTP auth performance
    if settings.TOKEN_CACHE_ENABLED:
        from app.middleware.auth import TokenCache
        mcp.token_cache = TokenCache(
            ttl_seconds=settings.TOKEN_CACHE_TTL_SECONDS,
            max_size=settings.TOKEN_CACHE_MAX_SIZE
        )
        logger.info(f"Token cache initialized (TTL: {settings.TOKEN_CACHE_TTL_SECONDS}s, max: {settings.TOKEN_CACHE_MAX_SIZE})")
    else:
        mcp.token_cache = None
        logger.info("Token cache disabled")

    registry = ToolRegistry()
    mcp.registry = registry
    logger.info("Registry created and attached to FastMCP instance")

    register_all_tools_metadata(
        registry=registry,
        user_service=user_service,
        memory_service=memory_service,
        project_service=project_service,
        code_artifact_service=code_artifact_service,
        document_service=document_service,
        entity_service=entity_service,
    )

    categories = registry.list_categories()
    total_tools = sum(categories.values())
    logger.info(f"Tool registration complete: {total_tools} tools across {len(categories)} categories")
    logger.info(f"Categories: {categories}")

    # Resolve instance-level scope ceiling
    from app.routes.mcp.scope_resolver import parse_scopes, resolve_permitted_tools
    instance_scopes = parse_scopes(settings.FORGETFUL_SCOPES)
    mcp._instance_permitted_tools = resolve_permitted_tools(instance_scopes, registry)
    mcp._instance_scopes = instance_scopes
    logger.info(f"Scoped permissions: scopes={list(instance_scopes)}, permitted_tools={len(mcp._instance_permitted_tools)}")

    yield

    logger.info("Shutting down session", extra={"service": settings.SERVICE_NAME})
    await db_adapter.dispose()
    logger.info("Database connections closed")
    logger.info("Session shutdown complete")


mcp = FastMCP(settings.SERVICE_NAME, lifespan=lifespan)


@mcp.custom_route("/", methods=["GET"])
async def root(request: Request) -> JSONResponse:
    """Root endpoint with basic service information."""
    logger.info("Root endpoint accessed")
    return JSONResponse({
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "health": "/health"
        }
    })


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


async def _run_reembed(args):
    """Run the re-embedding workflow"""
    from app.config.logging_config import configure_logging, shutdown_logging
    configure_logging(log_level="INFO", log_format="console")
    atexit.register(shutdown_logging)

    from app.services.re_embedding_service import ReEmbeddingService
    from app.services.backup_service import BackupService

    embeddings_adapter = _get_embedding_adapter()
    backup_service = BackupService()

    print("\n[1/5] Validating configuration...")
    print(f"  Provider: {settings.EMBEDDING_PROVIDER} ({settings.EMBEDDING_MODEL})")
    print(f"  Dimensions: {settings.EMBEDDING_DIMENSIONS}")
    if settings.DATABASE == "SQLite":
        print(f"  Database: SQLite ({settings.SQLITE_PATH})")
    else:
        print(f"  Database: PostgreSQL ({settings.POSTGRES_HOST}:{settings.PGPORT}/{settings.POSTGRES_DB})")
    print(f"  Batch size: {args.batch_size}")

    # Initialize database
    db_adapter = _create_db_adapter()

    if settings.DATABASE == "SQLite" and not settings.SQLITE_MEMORY:
        data_dir = Path(settings.SQLITE_PATH).parent
        data_dir.mkdir(parents=True, exist_ok=True)

    await db_adapter.init_db()

    # Create memory repository (reranker not needed for re-embedding)
    repos = _create_repositories(db_adapter, embeddings_adapter, None)
    memory_repository = repos["memory"]

    # Count memories for dry run / estimation
    total = await memory_repository.count_all_memories()
    print(f"  Memories to process: {total}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would re-embed {total} memories with the above configuration.")
        print("  No changes were made.")
        await db_adapter.dispose()
        return

    if total == 0:
        print("\n  No memories to re-embed. Done.")
        await db_adapter.dispose()
        return

    # Create backup (skip for in-memory SQLite)
    backup_path = None
    if settings.DATABASE == "SQLite" and settings.SQLITE_MEMORY:
        print("\n[2/5] Skipping backup (in-memory database)...")
    else:
        print("\n[2/5] Creating backup...")
        backup_path = await backup_service.create_backup()
        print(f"  Backup saved: {backup_path}")

    # Set up signal handling for graceful restore
    restore_triggered = False

    def signal_handler(signum, frame):
        nonlocal restore_triggered
        if restore_triggered:
            return
        restore_triggered = True
        print("\n\nInterrupted! Restoring from backup...")
        if backup_path:
            asyncio.get_event_loop().run_until_complete(
                backup_service.restore_backup(backup_path)
            )
            print(f"  Restored: {backup_path}")
        sys.exit(1)

    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Reset schema
        print("\n[3/5] Updating vector schema...")
        await memory_repository.reset_embedding_storage()
        if settings.DATABASE == "SQLite":
            print(f"  Recreated vec_memories table with {settings.EMBEDDING_DIMENSIONS} dimensions")
        else:
            print(f"  Altered embedding column to vector({settings.EMBEDDING_DIMENSIONS})")

        # Re-embed
        print("\n[4/5] Re-embedding memories...")

        def progress(processed, total_count):
            pct = int((processed / total_count) * 100) if total_count > 0 else 100
            bar_filled = int(pct / 4)
            bar = "\u2588" * bar_filled + "\u2591" * (25 - bar_filled)
            print(f"\r  [{bar}] {processed}/{total_count} memories ({pct}%)", end="", flush=True)

        service = ReEmbeddingService(
            memory_repository=memory_repository,
            embedding_adapter=embeddings_adapter,
            batch_size=args.batch_size,
        )

        result = await service.re_embed_all(progress_callback=progress)
        print()  # newline after progress bar

        # Validate
        print("\n[5/5] Validating...")
        if result.validation:
            print(f"  Count check: {result.total_memories} memories, "
                  f"{result.total_processed} embeddings "
                  f"{'✓' if result.validation.count_ok else '✗'}")
            print(f"  Dimension check: {'✓' if result.validation.dimensions_ok else '✗'}")
            print(f"  Search check: {'✓' if result.validation.search_ok else '✗'}")

            if not result.validation.all_passed:
                print("\n  Validation FAILED!")
                if backup_path:
                    print("  Restoring from backup...")
                    await backup_service.restore_backup(backup_path)
                    print(f"  Restored: {backup_path}")
                    print("  Database returned to pre-migration state.")
                await db_adapter.dispose()
                sys.exit(1)

        print(f"\n  Successfully re-embedded {result.total_processed} memories")
        if backup_path:
            print(f"  Backup retained at: {backup_path}")
            print("  (Delete manually when satisfied with results)")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        if backup_path:
            print("\n  Restoring from backup...")
            await backup_service.restore_backup(backup_path)
            print(f"  Restored: {backup_path}")
            print("  Database returned to pre-migration state.")
        await db_adapter.dispose()
        raise
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)

    await db_adapter.dispose()


def cli():
    """Command-line interface for running the Forgetful MCP server."""
    parser = argparse.ArgumentParser(
        description="Forgetful - MCP Server for AI Agent Memory"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method (default: stdio for MCP clients)"
    )
    parser.add_argument(
        "--host",
        default=settings.SERVER_HOST,
        help=f"HTTP host (default: {settings.SERVER_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.SERVER_PORT,
        help=f"HTTP port (default: {settings.SERVER_PORT})"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}"
    )

    # Re-embed arguments
    parser.add_argument(
        "--re-embed",
        action="store_true",
        help="Re-embed all memories with the currently configured provider"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Batch size for re-embedding (default: 20)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes"
    )

    args = parser.parse_args()

    if args.re_embed:
        asyncio.run(_run_reembed(args))
        return

    if args.transport == "stdio":
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        mcp.run(show_banner=False)
    elif not settings.CORS_ENABLED:
        # No CORS - use existing code path (zero behavioral change)
        mcp.run(transport="http", host=args.host, port=args.port, show_banner=False)
    else:
        # CORS enabled - use http_app with middleware
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware

        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=settings.CORS_ORIGINS,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=[
                    "mcp-protocol-version",
                    "mcp-session-id",
                    "Authorization",
                    "Content-Type",
                ],
                expose_headers=["mcp-session-id"],
            )
        ]

        import uvicorn
        app = mcp.http_app(middleware=middleware)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    cli()
