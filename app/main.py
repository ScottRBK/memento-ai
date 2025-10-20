"""
    FastAPI application for a python service 
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config.settings import settings
from app.routes.api.health import router as health_router 

import logging 

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """"Manages application lifecycle."""

    logger.info(f"Starting {settings.SERVICE_NAME}")

    yield 

    logger.info(f"Shutting down {settings.SERVICE_NAME}")

    logger.info(f"Shut down of {settings.SERVICE_NAME} completed") 


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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower()
    )
    
    


