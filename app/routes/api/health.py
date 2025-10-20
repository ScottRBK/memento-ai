"""
Health check endpoints for monitoring service status.
"""

from fastapi import APIRouter
from app.config.settings import settings
from app.models.models import HealthStatus 
from datetime import datetime, timezone
import logging


logger = logging.getLogger(__name__)


router = APIRouter()

@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
        Health check endpoint for the service
    """

    health_check = HealthStatus(
        status="healthy",
        timestamp= datetime.now(tz=timezone.utc),
        service = settings.SERVICE_NAME,
        version = settings.SERVICE_VERSION
    )
    logger.info(f"Health check response: {health_check}")

    return health_check


