"""
    FastAPI application for a python service 
"""
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


from app.config.settings import settings
from app.routes.api import health
# Postgres repositories
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.user_repository import PostgresUserRepository
from app.repositories.postgres.memory_repository import PostgresMemoryRepository
from app.repositories.postgres.project_repository import PostgresProjectRepository
from app.repositories.postgres.code_artifact_repository import PostgresCodeArtifactRepository
from app.repositories.postgres.document_repository import PostgresDocumentRepository
from app.repositories.postgres.entity_repository import PostgresEntityRepository
# SQLite repositories
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.user_repository import SqliteUserRepository
from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
from app.repositories.sqlite.project_repository import SqliteProjectRepository
from app.repositories.sqlite.code_artifact_repository import SqliteCodeArtifactRepository
from app.repositories.sqlite.document_repository import SqliteDocumentRepository
from app.repositories.sqlite.entity_repository import SqliteEntityRepository
# Shared
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter, AzureOpenAIAdapter
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.services.code_artifact_service import CodeArtifactService
from app.services.document_service import DocumentService
from app.services.entity_service import EntityService
from app.routes.mcp import meta_tools
from app.routes.mcp.tool_registry import ToolRegistry
from app.routes.mcp.tool_metadata_registry import register_all_tools_metadata
from app.config.logging_config import configure_logging, shutdown_logging

import logging 
import atexit 
queue_listener = configure_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)
atexit.register(shutdown_logging)


if settings.EMBEDDING_PROVIDER == "Azure":
    embeddings_adapter = AzureOpenAIAdapter()
else:
    embeddings_adapter = FastEmbeddingAdapter()

if settings.DATABASE == "Postgres":
    db_adapter = PostgresDatabaseAdapter()
    user_repository = PostgresUserRepository(db_adapter=db_adapter)
    memory_repository = PostgresMemoryRepository(
        db_adapter=db_adapter,
        embedding_adapter=embeddings_adapter
    )
    project_repository = PostgresProjectRepository(db_adapter=db_adapter)
    code_artifact_repository = PostgresCodeArtifactRepository(db_adapter=db_adapter)
    document_repository = PostgresDocumentRepository(db_adapter=db_adapter)
    entity_repository = PostgresEntityRepository(db_adapter=db_adapter)
elif settings.DATABASE == "SQLite":
    db_adapter = SqliteDatabaseAdapter()
    user_repository = SqliteUserRepository(db_adapter=db_adapter)
    memory_repository = SqliteMemoryRepository(
        db_adapter=db_adapter,
        embedding_adapter=embeddings_adapter
    )
    project_repository = SqliteProjectRepository(db_adapter=db_adapter)
    code_artifact_repository = SqliteCodeArtifactRepository(db_adapter=db_adapter)
    document_repository = SqliteDocumentRepository(db_adapter=db_adapter)
    entity_repository = SqliteEntityRepository(db_adapter=db_adapter)
else:
    raise ValueError(f"Unsupported DATABASE setting: {settings.DATABASE}. Must be 'Postgres' or 'SQLite'")

@asynccontextmanager
async def lifespan(app):
    """"Manages application lifecycle."""

    logger.info("Starting session", extra={"service": settings.SERVICE_NAME})

    # Initialize database FIRST
    await db_adapter.init_db()
    logger.info("Database Initialised")

    # Create services after DB is initialized
    user_service = UserService(user_repository)
    memory_service = MemoryService(memory_repository)
    project_service = ProjectService(project_repository)
    code_artifact_service = CodeArtifactService(code_artifact_repository)
    document_service = DocumentService(document_repository)
    entity_service = EntityService(entity_repository)

    # Store services on FastMCP instance for tool access (context pattern)
    mcp.user_service = user_service
    mcp.memory_service = memory_service
    mcp.project_service = project_service
    mcp.code_artifact_service = code_artifact_service
    mcp.document_service = document_service
    mcp.entity_service = entity_service
    logger.info("Services initialized and attached to FastMCP instance")

    # Create and attach registry
    registry = ToolRegistry()
    mcp.registry = registry
    logger.info("Registry created and attached to FastMCP instance")

    # Register all tools to registry (not exposed to MCP directly)
    register_all_tools_metadata(
        registry=registry,
        user_service=user_service,
        memory_service=memory_service,
        project_service=project_service,
        code_artifact_service=code_artifact_service,
        document_service=document_service,
        entity_service=entity_service,
    )

    # Log registration summary
    categories = registry.list_categories()
    total_tools = sum(categories.values())
    logger.info(f"Tool registration complete: {total_tools} tools across {len(categories)} categories")
    logger.info(f"Categories: {categories}")

    yield

    logger.info("Shutting down session", extra={"service": settings.SERVICE_NAME})
    await db_adapter.dispose()
    logger.info("Database connections closed")
    logger.info("Session shutdown complete")

logger.info("Registering MCP services")
mcp = FastMCP(settings.SERVICE_NAME, lifespan=lifespan)
logger.info("MCP services registered")


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

# API Routes
health.register(mcp)

# MCP Routes - Only register meta-tools (3 tools total)
# All other tools are accessible via execute_forgetful_tool
meta_tools.register(mcp)
logger.info("Meta-tools registered (discover_forgetful_tools, how_to_use_forgetful_tool, execute_forgetful_tool)")

if __name__ == "__main__":
    mcp.run(transport="http", host=settings.SERVER_HOST, port=settings.SERVER_PORT)
    
    


