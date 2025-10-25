"This module defines the models for the health service"

from pydantic import BaseModel, Field
from datetime import datetime

class HealthStatus(BaseModel):
    status: str = Field(..., description="Health Status of the Service", examples=["healthy", "unhealthy"])
    timestamp: datetime = Field(..., description="When the health check was performed", examples=["2024-12-30T20:12:25.673396"])
    service: str = Field(..., description="Name of the service", examples=["JWT Auth"])
    version: str = Field(..., description="Service version", examples=["v1.0.0"])


