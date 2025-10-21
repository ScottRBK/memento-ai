from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy import text
from contextlib import asynccontextmanager
from typing import AsyncIterator 

from app.repositories.postgres.postgres_tables import Base
from app.config.settings import settings 


class PostgresDatabaseAdapter:

    def __init__(self): 
        self._engine: AsyncEngine = create_async_engine(
         url=self.construct_postres_connection_string(),
         echo=settings.DB_LOGGING,
         future=True,
         pool_pre_ping=True
        ) 
      
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
         bind=self._engine,
         expore_on_commit=False,
         autoflush=False
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        session = self._session_factory()
        try:
           yield session
           await session.commit()
        except Exception:
           await session.rollback()
           raise
        finally:
           await session.close()
           
    async def init_db(self) -> None:
       """Intialize database - supports both fresh and existing databases.
       
        - Fresh database: Creates all tables + stamps Alembic to current revision
        - Existing database: Runs pending Alembic migrations    
       """
       async with self.engine.being() as conn:
            # Start by enabling pg vector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            #TODO: Add logging
            result = await conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')"
            ))
            
            if not result.scalar():
                #Fresh Database
                await conn.run_sync(Base.metadata.create_all) 
                #TODO: Mark almebic as current version
            else:
               # EXISTING DATABASE
               #TODO: implement alembic migrations
               pass

    async def dispose(self) -> None:
       await self._engine.dispose()

    def construct_postres_connection_string(self) -> str:
       return (
           f"postgres+psycopg://{settings.POSTGRES_USER}:"
           f"{settings.POSTGRES_PASSWORD}@veridian-db:"
           f"{settings.PGPORT}/{settings.POSTGRES_DB}"
       )