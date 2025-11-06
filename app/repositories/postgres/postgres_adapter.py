from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncIterator 
from uuid import UUID

from app.repositories.postgres.postgres_tables import Base
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
       """Intialize database - supports both fresh and existing databases.
       
        - Fresh database: Creates all tables + stamps Alembic to current revision
        - Existing database: Runs pending Alembic migrations    
       """
       async with self._engine.begin() as conn:
            # Start by enabling pg vector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("Intialising Database")
            result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
            ))
            
            if not result.scalar():
                #Fresh Database
                logger.info("Fresh database detected - creating schema")
                
                await conn.run_sync(Base.metadata.create_all) 
                
                logger.info("Database schema created successfully")
                
                #TODO: Mark almebic as current version
                logger.warning("Alembic version not set - alembic migrations not implemented yet")
            else:
               # EXISTING DATABASE
               logger.info("Existing Database Detected")
               #TODO: implement alembic migrations
               logger.warning("Alembic migration not applied, alembic migrations not implemented yet")
               pass

    async def dispose(self) -> None:
       await self._engine.dispose()

    def construct_postgres_connection_string(self) -> str:
       return (
           f"postgresql+asyncpg://{settings.POSTGRES_USER}:"
           f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
           f"{settings.PGPORT}/{settings.POSTGRES_DB}"
       )