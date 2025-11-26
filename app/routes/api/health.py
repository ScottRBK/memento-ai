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
        Health check endpoint for the service.

        Returns 503 until lifespan() completes and services are attached to mcp.
        Returns 200 once fully initialized.
        """
        # Check if services have been initialized (set at end of lifespan)
        if not hasattr(mcp, 'memory_service') or mcp.memory_service is None:
            logger.warning("Service initialising: services not yet attached")
            return JSONResponse(
                {
                    "status": "initialising",
                    "message": "Service starting",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": settings.SERVICE_NAME,
                    "version": settings.SERVICE_VERSION
                },
                status_code=503
            )

        health_status = HealthStatus(
            status="healthy",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            service=settings.SERVICE_NAME,
            version=settings.SERVICE_VERSION
        )
        logger.info("Health check completed", extra={"status": health_status.status})

        return JSONResponse(health_status.model_dump(mode="json"))
        





