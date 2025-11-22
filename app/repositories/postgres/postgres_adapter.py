from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncIterator 
from uuid import UUID

from app.config.settings import settings 

import logging
logger = logging.getLogger(__name__)

class PostgresDatabaseAdapter:

    def __init__(self): 
        self._engine: AsyncEngine = create_async_engine(
         url=self.construct_postgres_connection_string(),
         echo=settings.DB_LOGGING,
         future=True,
         pool_pre_ping=True
        ) 
      
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
         bind=self._engine,
         expire_on_commit=False,
         autoflush=False
        )

    @asynccontextmanager
    async def session(self, user_id: UUID)-> AsyncIterator[AsyncSession]:
      """Create a user-scoped session with RLS context"""
      session = self._session_factory()
      try:
         await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id)}
         )
         yield session
         await session.commit()
      except Exception as e:
         logger.exception(
            msg="Database session intialisation failed",
            extra={"error": str(e)})
         await session.rollback()
         raise
      finally:
         await session.close()

    @asynccontextmanager
    async def system_session(self) -> AsyncIterator[AsyncSession]:
       """Create a system session (no RLS) for admin operations"""
       session = self._session_factory()  # Same factory, no RLS context
       try:
           yield session
           await session.commit()
       except Exception as e:
           logger.exception(
            msg="Database system session intialisation failed",
            extra={"error": str(e)})
           await session.rollback()
           raise
       finally:
           await session.close()
           
    async def init_db(self) -> None:
        """Initialize database via Alembic migrations.

        Alembic handles both fresh and existing databases:
        - Fresh database: Creates full schema via migrations
        - Existing database: Runs pending migrations
        """
        async with self._engine.begin() as conn:
            # Enable pg_vector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("Initializing Database")

            # Run migrations (Alembic handles fresh vs existing database)
            await conn.run_sync(self._run_migrations)
            logger.info("Database schema initialized via Alembic")

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
            self.construct_postgres_connection_string()
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
            self.construct_postgres_connection_string()
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
       await self._engine.dispose()

    def construct_postgres_connection_string(self) -> str:
       return (
           f"postgresql+asyncpg://{settings.POSTGRES_USER}:"
           f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
           f"{settings.PGPORT}/{settings.POSTGRES_DB}"
       )