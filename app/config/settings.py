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
    SERVICE_NAME: str = "Memento"
    SERVICE_VERSION: str = "v0.0.1"
    SERVICE_DESCRIPTION: str = "Memento Memory Service"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8020
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    DATABASE: str = "Postgres"
    PGPORT: int = 5099
    POSTGRES_DB: str = "memento"
    POSTGRES_USER: str = "memento"
    POSTGRES_PASSWORD: str = "memento"
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
