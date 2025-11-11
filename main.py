"""
    FastAPI application for a python service 
"""
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


from app.config.settings import settings
from app.routes.api import health 
from app.middleware.auth import init_auth
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.user_repository import PostgresUserRepository
from app.repositories.postgres.memory_repository import PostgresMemoryRepository
from app.repositories.postgres.project_repository import PostgresProjectRepository
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter
from app.services.user_service import UserService
from app.services.memory_service import MemoryService
from app.services.project_service import ProjectService
from app.routes.mcp import user_tools, memory_tools, project_tools
from app.config.logging_config import configure_logging, shutdown_logging

import logging 
import atexit 
queue_listener = configure_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)
atexit.register(shutdown_logging)

if settings.DATABASE == "Postgres":
    db_adapter = PostgresDatabaseAdapter()
    user_repository = PostgresUserRepository(db_adapter=db_adapter)
    embeddings_adapter = FastEmbeddingAdapter()
    memory_repository = PostgresMemoryRepository(
        db_adapter=db_adapter,
        embedding_adapter=embeddings_adapter
    )
    project_repository = PostgresProjectRepository(db_adapter=db_adapter)

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

    # Store services on FastMCP instance for tool access
    mcp.memory_service = memory_service
    mcp.project_service = project_service

    # Initialize auth with user service
    init_auth(user_service=user_service)
    logger.info("MCP Authentication Enabled")

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

# MCP Routes
user_tools.register(mcp)
memory_tools.register(mcp)
project_tools.register(mcp)

if __name__ == "__main__":
    mcp.run(transport="http", host=settings.SERVER_HOST, port=settings.SERVER_PORT)
    
    


