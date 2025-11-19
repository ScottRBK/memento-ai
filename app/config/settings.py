"""
    Configuration Management For the Service
"""
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from platformdirs import user_data_dir, user_config_dir

load_dotenv()

# Platform-specific default paths
_default_data_dir = Path(user_data_dir("forgetful", ensure_exists=False))
_default_config_dir = Path(user_config_dir("forgetful", ensure_exists=False))


class Settings(BaseSettings):
    # Application Info
    SERVICE_NAME: str = "Forgetful"
    SERVICE_VERSION: str = "v0.0.1"
    SERVICE_DESCRIPTION: str = "Forgetful Memory Service"

    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8020
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"

    # Database Configuration
    DATABASE: str = "SQLite"  # "Postgres" or "SQLite"

    # Postgres Configuration
    POSTGRES_HOST: str = "127.0.0.1"  # 127.0.0.1 for local, forgetful-db for Docker
    PGPORT: int = 5099
    POSTGRES_DB: str = "forgetful"
    POSTGRES_USER: str = "forgetful"
    POSTGRES_PASSWORD: str = "forgetful"

    # SQLite Configuration
    SQLITE_PATH: str = str(_default_data_dir / "forgetful.db")  # Platform-specific path
    SQLITE_MEMORY: bool = False  # Use :memory: database (for testing)

    DB_LOGGING: bool = False

    # Auth Configuration
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

    # Project Configuration
    PROJECT_DESCRIPTION_MAX_LENGTH: int = 5000  # Text field, no DB limit - reasonable cap
    PROJECT_NOTES_MAX_LENGTH: int = 4000        # Text field, no DB limit - reasonable cap

    # Code Artifact Configuration
    CODE_ARTIFACT_TITLE_MAX_LENGTH: int = 500         # DB limit: String(500)
    CODE_ARTIFACT_DESCRIPTION_MAX_LENGTH: int = 5000  # Reasonable cap for text field
    CODE_ARTIFACT_CODE_MAX_LENGTH: int = 50000        # ~50KB for large code snippets
    CODE_ARTIFACT_TAGS_MAX_COUNT: int = 10            # For categorization

    # Document Configuration
    DOCUMENT_TITLE_MAX_LENGTH: int = 500         # DB limit: String(500)
    DOCUMENT_DESCRIPTION_MAX_LENGTH: int = 5000  # Reasonable cap for text field
    DOCUMENT_CONTENT_MAX_LENGTH: int = 100000    # ~100KB for large documents
    DOCUMENT_TAGS_MAX_COUNT: int = 10            # For categorization

    # Entity Configuration
    ENTITY_NAME_MAX_LENGTH: int = 200            # DB limit: String(200)
    ENTITY_TYPE_MAX_LENGTH: int = 100            # For custom entity types
    ENTITY_NOTES_MAX_LENGTH: int = 4000          # Reasonable cap for text field
    ENTITY_TAGS_MAX_COUNT: int = 10              # For categorization
    ENTITY_RELATIONSHIP_TYPE_MAX_LENGTH: int = 100  # e.g., "works_at", "owns", "manages"

    # Search Configuration
    EMBEDDING_PROVIDER: str = "FastEmbed" # FastEmbed | Azure | Google
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSIONS: int = 384
    DENSE_SEARCH_CANDIDATES: int = 50     # number of candidates to retrieve from the dense search
    
    # AZURE EMBEDDING PROVIDER CONFIG
    AZURE_ENDPOINT: str = ""
    AZURE_DEPLOYMENT: str = ""
    AZURE_API_VERSION: str = ""
    AZURE_API_KEY: str = ""
    
    # GOOGLE EMBEDDING PROVIDER CONFIG
    GOOGLE_AI_API_KEY: str = ""

    # RERANKING 
    RERANKING_ENABLED: bool = True
    RERANKING_PROVIDER: str = "FastEmbed"
    RERANKING_MODEL: str = "Xenova/ms-marco-MiniLM-L-12-v2"

    """Pydantic Configuration"""

    model_config = ConfigDict(
        env_file=[
            ".env",  # Local override
            "docker/.env",  # Development/Docker
            str(_default_config_dir / ".env"),  # User config
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
