"""
    Configuration Management For the Service
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "example")


class Settings(BaseSettings):
    # Application Info
    SERVICE_NAME: str = "Memento"
    SERVICE_VERSION: str = "v0.0.1"
    SERVICE_DESCRIPTION: str = "Memento Memory Service"

    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8020
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"

    # Database Configuration
    DATABASE: str = "Postgres"
    POSTGRES_HOST: str = "127.0.0.1"  # 127.0.0.1 for local, memento-db for Docker
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

    # Memory Configuration
    MEMORY_TITLE_MAX_LENGTH: int = 200      # Must be "easily titled" - scannable
    MEMORY_CONTENT_MAX_LENGTH: int = 2000   # ~300-400 words - single concept
    MEMORY_CONTEXT_MAX_LENGTH: int = 500    # Brief contextual description
    MEMORY_KEYWORDS_MAX_COUNT: int = 10     # For semantic clustering
    MEMORY_TAGS_MAX_COUNT: int = 10         # For categorization
    MEMORY_TOKEN_BUDGET: int = 8000         # token budget for retrieved memories (to protect context window)
    MEMORY_MAX_MEMORIES: int = 20           # maximum number of memories that can be retrieved from a query
    MEMORY_NUM_AUTO_LINK: int = 3           # number of memories to automatically link
    
    # Search Configuration
    EMBEDDING_PROVIDER: str = "FastEmbed"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384


    """Pydantic Configuration"""

    model_config = ConfigDict(
        env_file=f"docker/.env.{ENVIRONMENT}",
        extra="ignore"
    )

settings = Settings()
