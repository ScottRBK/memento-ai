"""
    Configuration Management For the Service
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


class Settings(BaseSettings):

    # Application Info
    SERVICE_NAME: str = "Python Template"
    SERVICE_VERSION: str = "v0.1.0"
    SERVICE_DESCRIPTION: str= "Python FastAPI Template Service"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8020
    LOG_LEVEL: str = "INFO"


    """Pydantic Configuration"""

    model_config = ConfigDict(
        env_file=f".env.{ENVIRONMENT}",
        extra="ignore"
    )

settings = Settings()
