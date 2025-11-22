from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy import text, event
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID
import sqlite_vec

from app.config.settings import settings

import logging

logger = logging.getLogger(__name__)


def _sqlite_connection_creator():
    """
    Create a SQLite connection with sqlite-vec extension loaded.
    This is used as a creator function for SQLAlchemy's engine.
    """
    import sqlite3

    # Construct connection string
    if settings.SQLITE_MEMORY:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
    else:
        conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)

    # Load sqlite-vec extension
    conn.enable_load_extension(True)
    conn.load_extension(sqlite_vec.loadable_path())
    conn.enable_load_extension(False)

    # Set pragmas
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    return conn


class SqliteDatabaseAdapter:
    """
    SQLite database adapter for async operations.

    Key differences from Postgres:
    - No Row-Level Security (RLS) - user isolation via application-level filtering
    - Uses sqlite-vec extension for vector operations
    - WAL mode enabled for better concurrency
    - No connection pooling (SQLite single writer model)
    """

    def __init__(self):
        
        if not settings.SQLITE_MEMORY:
            from pathlib import Path
            db_path = Path(settings.SQLITE_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("Validated DB directory exists", extra={
                "SQL Lite Path": settings.SQLITE_PATH
            })
        # Construct connection string
        connection_string = self._construct_connection_string()

        # Create async engine with SQLite-specific settings
        self._engine: AsyncEngine = create_async_engine(
            url=connection_string,
            echo=settings.DB_LOGGING,
            future=True,
            # SQLite-specific: disable pooling for better behavior
            poolclass=None,  # No connection pool for SQLite
            connect_args={
                "check_same_thread": False,  # Required for async
            },
        )

        # Register event to load extension on EVERY connection (not just first)
        # This is critical since poolclass=None means each session gets a new connection
        @event.listens_for(self._engine.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Load sqlite-vec extension on every connection"""
            # For aiosqlite, dbapi_conn is AsyncAdapt_aiosqlite_connection
            # Access the underlying aiosqlite Connection via _connection
            if hasattr(dbapi_conn, "_connection"):
                aio_conn = dbapi_conn._connection
                # aiosqlite.Connection has a _conn attribute with the raw sqlite3.Connection
                if hasattr(aio_conn, "_conn"):
                    raw_conn = aio_conn._conn
                    # Load extension on raw connection
                    raw_conn.enable_load_extension(True)
                    raw_conn.load_extension(sqlite_vec.loadable_path())
                    raw_conn.enable_load_extension(False)
                    # Set pragmas
                    raw_conn.execute("PRAGMA journal_mode=WAL")
                    raw_conn.execute("PRAGMA synchronous=NORMAL")
                    raw_conn.execute("PRAGMA foreign_keys=ON")
                    raw_conn.execute("PRAGMA busy_timeout=5000")
                    logger.debug("sqlite-vec extension loaded on connection")

        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine, expire_on_commit=False, autoflush=False
        )

    @asynccontextmanager
    async def session(self, user_id: UUID) -> AsyncIterator[AsyncSession]:
        """
        Create a user-scoped session.

        Note: Unlike Postgres, SQLite doesn't have RLS.
        User isolation MUST be enforced at the application level
        by including user_id in all WHERE clauses.
        """
        session = self._session_factory()
        try:
            # No RLS setup needed - user filtering happens in queries
            yield session
            await session.commit()
        except Exception as e:
            logger.exception(
                msg="Database session initialization failed", extra={"error": str(e)}
            )
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def system_session(self) -> AsyncIterator[AsyncSession]:
        """Create a system session for admin operations"""
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.exception(
                msg="Database system session initialization failed",
                extra={"error": str(e)},
            )
            await session.rollback()
            raise
        finally:
            await session.close()

    async def init_db(self) -> None:
        """Initialize database via Alembic migrations.

        Alembic handles both fresh and existing databases:
        - Fresh database: Creates full schema via migrations
        - Existing database: Runs pending migrations

        Note: sqlite-vec extension is loaded automatically via event listener on first connection
        """
        async with self._engine.begin() as conn:
            logger.info("Initializing SQLite database")

            # Run migrations (Alembic handles fresh vs existing database)
            await conn.run_sync(self._run_migrations)
            logger.info("Database schema initialized via Alembic")

            # Create virtual table for vector storage (not managed by Alembic)
            await conn.execute(
                text(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories USING vec0(
                    memory_id TEXT PRIMARY KEY,
                    embedding FLOAT[{settings.EMBEDDING_DIMENSIONS}]
                )
            """)
            )
            logger.info("sqlite-vec virtual table created for vector storage")

    def _run_migrations(self, connection) -> None:
        """Run pending Alembic migrations synchronously (called via run_sync)."""
        from alembic.config import Config
        from alembic import command
        from pathlib import Path

        # Find alembic.ini relative to package root
        package_root = Path(__file__).parent.parent.parent.parent
        alembic_ini = package_root / "alembic.ini"

        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini))

        # Override database URL in config
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            self._construct_connection_string()
        )

        # Configure to use existing connection
        alembic_cfg.attributes['connection'] = connection

        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic upgrade completed successfully")
        except Exception as e:
            logger.error(f"Alembic migration failed: {e}", exc_info=True)
            raise

    def _stamp_db(self, connection) -> None:
        """Stamp database with current Alembic revision (called via run_sync)."""
        from alembic.config import Config
        from alembic import command
        from pathlib import Path

        # Find alembic.ini relative to package root
        package_root = Path(__file__).parent.parent.parent.parent
        alembic_ini = package_root / "alembic.ini"

        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            self._construct_connection_string()
        )

        # Configure to use existing connection
        alembic_cfg.attributes['connection'] = connection

        try:
            command.stamp(alembic_cfg, "head")
            logger.info("Database stamped with current Alembic revision")
        except Exception as e:
            logger.error(f"Failed to stamp database: {e}", exc_info=True)
            raise

    async def dispose(self) -> None:
        """Dispose of the database engine and close all connections"""
        await self._engine.dispose()

    def _construct_connection_string(self) -> str:
        """Construct SQLite connection string"""
        if settings.SQLITE_MEMORY:
            # In-memory database (for testing)
            return "sqlite+aiosqlite:///:memory:"
        else:
            # File-based database
            return f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"
