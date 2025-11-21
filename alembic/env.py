"""Alembic environment configuration for async SQLAlchemy migrations.

Supports both Postgres and SQLite with conditional configuration.
"""
import asyncio
from logging.config import fileConfig
from pathlib import Path
import sys

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.repositories.postgres.postgres_tables import Base as PostgresBase
from app.repositories.sqlite.sqlite_tables import Base as SqliteBase

# This is the Alembic Config object
config = context.config

# Setup target metadata based on database type
if settings.DATABASE == "Postgres":
    target_metadata = PostgresBase.metadata
else:  # SQLite
    target_metadata = SqliteBase.metadata

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL scripts without executing).

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the create_engine()
    step we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    if settings.DATABASE == "Postgres":
        sqlalchemy_url = (
            f"postgresql+asyncpg://{settings.POSTGRES_USER}:"
            f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
            f"{settings.PGPORT}/{settings.POSTGRES_DB}"
        )
    else:  # SQLite
        sqlalchemy_url = f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"

    context.configure(
        url=sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect type changes
        compare_server_default=True,  # Detect default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations synchronously within an async context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # Important for catching type changes
        compare_server_default=True,  # Catch default value changes
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    # Build database URL based on settings
    if settings.DATABASE == "Postgres":
        sqlalchemy_url = (
            f"postgresql+asyncpg://{settings.POSTGRES_USER}:"
            f"{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:"
            f"{settings.PGPORT}/{settings.POSTGRES_DB}"
        )
    else:  # SQLite
        sqlalchemy_url = f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"

    # Override the sqlalchemy.url in the alembic config
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = sqlalchemy_url
    configuration["sqlalchemy.echo"] = str(settings.DB_LOGGING)

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Load sqlite-vec extension for SQLite (if using SQLite)
    if settings.DATABASE == "SQLite":
        from sqlalchemy import event
        import sqlite_vec

        @event.listens_for(connectable.sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            """Load sqlite-vec extension on every connection"""
            if hasattr(dbapi_conn, "_connection"):
                aio_conn = dbapi_conn._connection
                if hasattr(aio_conn, "_conn"):
                    raw_conn = aio_conn._conn
                    raw_conn.enable_load_extension(True)
                    raw_conn.load_extension(sqlite_vec.loadable_path())
                    raw_conn.enable_load_extension(False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Supports two execution modes:
    1. CLI usage (alembic upgrade head) - creates new engine with asyncio.run()
    2. Adapter usage (from init_db) - uses provided connection synchronously
    """
    # Check if connection provided via attributes (from adapter)
    connectable = config.attributes.get('connection', None)

    if connectable is not None:
        # Use existing connection (sync context from run_sync)
        do_run_migrations(connectable)
    else:
        # Create new engine (command-line usage)
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
