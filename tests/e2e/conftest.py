"""
E2E test fixtures with real PostgreSQL in Docker
"""
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.config.settings import settings


@pytest.fixture(scope="module")
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def test_database():
    """
    Creates a test database in PostgreSQL for E2E tests.

    Requires PostgreSQL to be running (via Docker or locally).
    Uses POSTGRES_DB=memento_test from settings.
    """
    # Create engine for postgres database (to create test db)
    admin_url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@127.0.0.1:{settings.PGPORT}/postgres"
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    # Drop and recreate test database
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {settings.POSTGRES_DB}"))
        await conn.execute(text(f"CREATE DATABASE {settings.POSTGRES_DB}"))

    await admin_engine.dispose()

    # Initialize test database schema
    from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter

    db_adapter = PostgresDatabaseAdapter()
    await db_adapter.init_db()

    yield db_adapter

    # Cleanup
    await db_adapter.dispose()

    # Drop test database
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {settings.POSTGRES_DB}"))
    await admin_engine.dispose()


@pytest.fixture
def mcp_server_url():
    """Returns the URL of the running MCP server for E2E tests"""
    return f"http://127.0.0.1:{settings.PORT}"


@pytest.fixture
async def cleanup_test_users(test_database):
    """Cleans up test users after E2E tests"""
    yield

    # Cleanup users created during tests
    async with test_database.session() as session:
        await session.execute(text("DELETE FROM users WHERE external_id LIKE 'test-%'"))
        await session.commit()
