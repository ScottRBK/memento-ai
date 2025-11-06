"""
Health check endpoints for monitoring service status.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from fastmcp import FastMCP

from app.config.settings import settings
from app.models.models import HealthStatus 
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def register(mcp: FastMCP):
    """Register health check routes with FastMCP"""

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        """
        Health check endpoint for the service
        """
        try:
            from main import embeddings_adapter
            if embeddings_adapter.model is None:
                return JSONResponse(
                    {
                        "status": "intialising",
                        "message": "Embedding model loading",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": settings.SERVICE_NAME,
                        "version": settings.SERVICE_VERSION
                    }, 
                    status_code=503
                )
        except Exception as e:
            logger.warning(f"Service initialising: {str(e)}")
            return JSONResponse(
                    {
                        "status": "intialising",
                        "message": "Service starting",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": settings.SERVICE_NAME,
                        "version": settings.SERVICE_VERSION
                    }, 
                    status_code=503
                )

        health_status = HealthStatus(
            status="healthy",
            timestamp= datetime.now(tz=timezone.utc).isoformat(),
            service = settings.SERVICE_NAME,
            version = settings.SERVICE_VERSION
        )
        logger.info("Health check completed", extra={"status": health_status.status})

        return JSONResponse(health_status.model_dump(mode="json"))
        





