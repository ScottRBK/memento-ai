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
    SERVICE_DESCRIPTION: str = "Python FastAPI Template Service"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8020
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    DATABASE: str = "Postgres"
    PGPORT: int = 5099
    POSTGRES_DB: str = "veridian"
    POSTGRES_USER: str = "veridian"
    POSTGRES_PASSWORD: str = "veridian"
    DB_LOGGING: bool = False

    # Auth Configuration
    AUTH_ENABLED: bool = False
    DEFAULT_USER_ID: str = "default-user-id"
    DEFAULT_USER_NAME: str = "default-user-name"
    DEFAULT_USER_EMAIL: str = "default-user-email"

    """Pydantic Configuration"""

    model_config = ConfigDict(
        env_file=f".env.{ENVIRONMENT}",
        extra="ignore"
    )

settings = Settings()
