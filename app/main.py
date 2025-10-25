"""
    FastAPI application for a python service 
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastmcp import FastMCP
from app.config.settings import settings
from app.routes.api.health import router as health_router 
from app.middleware.auth import init_auth
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.user_repository import PostgresUserRepository  
from app.services.user_service import UserService
from app.routes.mcp import user_tools
from app.config.logging_config import configure_logging, shutdown_logging

import logging 
queue_listener = configure_logging(
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

if settings.DATABASE == "Postgres":
    db_adapter = PostgresDatabaseAdapter()
    user_repository = PostgresUserRepository(db_adapter=db_adapter) 


@asynccontextmanager
async def lifespan(app: FastAPI):
    """"Manages application lifecycle."""

    logger.info("Starting service", extra={"service": settings.SERVICE_NAME}) 
    await db_adapter.init_db()
    logger.info("Database Initialised")
    
    user_service = UserService(user_repository)
    init_auth(user_service=user_service)
    logger.info("MCP Authentication Enabled")
 
    yield 

    logger.info("Shutting down", extra={"service": settings.SERVICE_NAME})
    await db_adapter.dispose()
    logger.info("Database connections closed") 
    
    logger.info("Shutdown complete")
    shutdown_logging()


app = FastAPI(
    title = settings.SERVICE_NAME,
    description = settings.SERVICE_DESCRIPTION,
    version = settings.SERVICE_VERSION,
    docs_url = "/docs",
    redoc_url = "/redoc",
    lifespan=lifespan
)

app.include_router(health_router)

@app.get("/")
async def root():
    """Root endpoint with basic service information."""
    logger.info("Root endpoint accessed")
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "health": "/health"
        }
    }

logger.info("Registering MCP services")
mcp = FastMCP(settings.SERVICE_NAME, lifespan=lifespan)
logger.info("MCP services registered")

user_tools.register(mcp)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.SERVER_PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
    
    


