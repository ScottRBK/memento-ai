"""
SQLite Database Adapter

Provides async database connection and session management for SQLite backend.
Note: SQLite doesn't support Row-Level Security (RLS), so user isolation is
handled at the application level through query filtering.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy import text, event
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID
import logging

from app.config.settings import settings

logger = logging.getLogger(__name__)


class SqliteDatabaseAdapter:
    """
    SQLite database adapter with async support via aiosqlite.

    Key differences from Postgres:
    - No Row-Level Security (RLS) - user filtering done in queries
    - Single-writer database (no connection pooling benefits)
    - WAL mode enabled for better concurrency
    - sqlite-vec extension for vector similarity search
    """

    def __init__(self):
        connection_string = self._construct_sqlite_connection_string()

        self._engine: AsyncEngine = create_async_engine(
            url=connection_string,
            echo=settings.DB_LOGGING,
            future=True,
            # SQLite-specific optimizations
            connect_args={
                "check_same_thread": False,  # Allow async usage
            },
            # Disable pooling for SQLite (single writer)
            poolclass=None if settings.SQLITE_PATH == ":memory:" else None,
        )

        # Enable WAL mode and load sqlite-vec extension on connect
        @event.listens_for(self._engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # Enable Write-Ahead Logging for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys=ON")
            # Load sqlite-vec extension for vector similarity search
            try:
                # The extension should be available in the environment
                # sqlite-vec typically loads automatically with the package
                cursor.execute("SELECT load_extension('vec0')")
                logger.debug("sqlite-vec extension loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load sqlite-vec extension: {e}. Vector search may not work.")
            cursor.close()

        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False
        )

    @asynccontextmanager
    async def session(self, user_id: UUID) -> AsyncIterator[AsyncSession]:
        """
        Create a user-scoped session for database operations.

        Note: Unlike Postgres, SQLite doesn't support Row-Level Security.
        User isolation MUST be enforced in queries using WHERE clauses.
        The user_id parameter is kept for API compatibility but doesn't
        set any database-level context.

        Args:
            user_id: User ID for API compatibility (not used for RLS)

        Yields:
            AsyncSession: Database session for this user's operations
        """
        session = self._session_factory()
        try:
            # SQLite doesn't support RLS - user_id filtering must be in queries
            # We store user_id as session info for debugging/logging purposes
            session.info["user_id"] = str(user_id)
            yield session
            await session.commit()
        except Exception as e:
            logger.exception(
                msg="Database session initialization failed",
                extra={"error": str(e), "user_id": str(user_id)}
            )
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def system_session(self) -> AsyncIterator[AsyncSession]:
        """
        Create a system session for admin operations.

        For SQLite, this is identical to a regular session since there's
        no RLS to bypass. Kept for API compatibility with Postgres adapter.

        Yields:
            AsyncSession: Database session for system operations
        """
        session = self._session_factory()
        try:
            session.info["is_system"] = True
            yield session
            await session.commit()
        except Exception as e:
            logger.exception(
                msg="Database system session initialization failed",
                extra={"error": str(e)}
            )
            await session.rollback()
            raise
        finally:
            await session.close()

    async def init_db(self) -> None:
        """
        Initialize database - creates tables if they don't exist.

        For SQLite:
        - Creates database file if it doesn't exist
        - Creates all tables using SQLAlchemy metadata
        - Enables WAL mode and foreign keys (via connect event)
        - Attempts to load sqlite-vec extension

        Note: Alembic migrations not yet implemented for SQLite.
        """
        # Import Base from sqlite_tables (will create after this file)
        from app.repositories.sqlite.sqlite_tables import Base

        async with self._engine.begin() as conn:
            logger.info("Initializing SQLite database")

            # Check if tables exist (check for users table as indicator)
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ))

            if not result.scalar():
                # Fresh database - create all tables
                logger.info("Fresh database detected - creating schema")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database schema created successfully")

                # TODO: Implement Alembic migrations for SQLite
                logger.warning("Alembic migrations not implemented for SQLite yet")
            else:
                # Existing database
                logger.info("Existing database detected")
                # TODO: Implement Alembic migrations for SQLite
                logger.warning("Alembic migrations not implemented for SQLite yet")

    async def dispose(self) -> None:
        """Dispose of the database engine and close all connections."""
        await self._engine.dispose()

    def _construct_sqlite_connection_string(self) -> str:
        """
        Construct SQLite connection string for aiosqlite.

        Formats:
        - File-based: sqlite+aiosqlite:///path/to/database.db
        - In-memory: sqlite+aiosqlite:///:memory:

        Returns:
            str: SQLAlchemy connection string
        """
        if settings.SQLITE_PATH == ":memory:":
            connection_string = "sqlite+aiosqlite:///:memory:"
        else:
            # Use absolute path or relative to working directory
            connection_string = f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"

        logger.info(f"SQLite connection: {connection_string}")
        return connection_string
