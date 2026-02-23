"""
E2E tests for PostgreSQL backup and restore via BackupService.

Tests the full backup/restore cycle with real pg_dump/psql to verify
that --clean flag produces restorable dumps when tables already exist.
"""
import shutil

import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.memory_models import MemoryCreate
from app.repositories.postgres.memory_repository import PostgresMemoryRepository
from app.services.backup_service import BackupService

pytestmark = [
    pytest.mark.asyncio(loop_scope="session"),
    pytest.mark.skipif(
        shutil.which("pg_dump") is None,
        reason="pg_dump not found — install postgresql-client to run backup tests",
    ),
]


@pytest_asyncio.fixture(loop_scope="session")
async def memory_repo(db_adapter, embedding_adapter):
    """Repo using the configured embedding adapter."""
    repo = PostgresMemoryRepository(
        db_adapter=db_adapter,
        embedding_adapter=embedding_adapter,
        rerank_adapter=None,
    )
    yield repo


async def _restore_and_recycle_pool(backup_service, backup_path, db_adapter):
    """Restore from backup then recycle the connection pool.

    pg_dump --clean generates DROP/CREATE statements that invalidate
    PostgreSQL type OID caches in existing connections. We must:
    1. Close all pooled connections (so psql doesn't fight locks)
    2. Run the restore
    3. Pool auto-rebuilds with fresh connections on next use
    """
    await db_adapter._engine.dispose()
    await backup_service.restore_backup(backup_path)


async def _fresh_query(db_adapter, sql, params=None):
    """Run a query on a throwaway engine to avoid cached statement issues."""
    engine = create_async_engine(
        url=db_adapter.construct_postgres_connection_string(),
        echo=False,
    )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params or {})
            return result.scalar()
    finally:
        await engine.dispose()


async def _create_user(db_adapter, user_id):
    """Create a user row in the database (required for FK constraints)."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    async with db_adapter.system_session() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, external_id, name, email, created_at, updated_at) "
                "VALUES (:id, :external_id, :name, :email, :created_at, :updated_at)"
            ),
            {
                "id": str(user_id),
                "external_id": f"ext-{user_id}",
                "name": "Test User",
                "email": "test@example.com",
                "created_at": now,
                "updated_at": now,
            },
        )


async def _create_test_memories(repo, db_adapter, count=3):
    """Helper to create test memories with embeddings."""
    user_id = uuid4()
    await _create_user(db_adapter, user_id)

    memories = []
    for i in range(count):
        memory = await repo.create_memory(
            user_id=user_id,
            memory=MemoryCreate(
                title=f"Backup Test Memory {i}",
                content=f"Content for backup test memory {i}",
                context=f"Context for backup test {i}",
                keywords=[f"backup{i}", "test"],
                tags=[f"tag{i}", "test"],
                importance=7,
            ),
        )
        memories.append(memory)
    return user_id, memories


async def _truncate_memories(db_adapter):
    """Truncate memories table for test isolation."""
    async with db_adapter.system_session() as session:
        await session.execute(text("TRUNCATE memories, users CASCADE"))


@pytest.mark.e2e
async def test_backup_and_restore_after_schema_modification(memory_repo, db_adapter, embedding_adapter):
    """
    Verify backup restores correctly after schema has been modified.

    This is the exact scenario that occurs during a failed re-embed:
    1. Memories exist with embeddings
    2. Backup is taken
    3. Schema is modified (embedding column altered)
    4. Something fails — restore from backup
    5. Original data and schema should be intact
    """
    await _truncate_memories(db_adapter)
    user_id, memories = await _create_test_memories(memory_repo, db_adapter, count=3)

    # Verify memories exist with embeddings before backup
    async with db_adapter.system_session() as session:
        result = await session.execute(
            text("SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
        )
        assert result.scalar() == 3

    # Create backup
    backup_service = BackupService(database_type="Postgres")
    backup_path = await backup_service.create_backup()
    assert backup_path.exists()

    try:
        # Simulate re-embed step 3: modify schema (clear embeddings, alter column)
        async with db_adapter.system_session() as session:
            await session.execute(text(
                "ALTER TABLE memories ALTER COLUMN embedding DROP NOT NULL"
            ))
            await session.execute(text(
                "UPDATE memories SET embedding = NULL"
            ))

        # Verify schema was modified (embeddings are gone)
        async with db_adapter.system_session() as session:
            result = await session.execute(
                text("SELECT count(*) FROM memories WHERE embedding IS NOT NULL")
            )
            assert result.scalar() == 0

        # Restore from backup — recycles pool to avoid stale cached statements
        await _restore_and_recycle_pool(backup_service, backup_path, db_adapter)

        # Verify data is restored (fresh connection avoids OID cache issues)
        count = await _fresh_query(
            db_adapter,
            "SELECT count(*) FROM memories WHERE embedding IS NOT NULL",
        )
        assert count == 3

        # Verify memory content is intact
        for original in memories:
            title = await _fresh_query(
                db_adapter,
                "SELECT title FROM memories WHERE id = :id",
                {"id": original.id},
            )
            assert title == original.title

    finally:
        backup_path.unlink(missing_ok=True)


@pytest.mark.e2e
async def test_backup_and_restore_with_data_changes(memory_repo, db_adapter, embedding_adapter):
    """
    Verify backup restores to the point-in-time state, discarding
    data added after the backup was taken.
    """
    await _truncate_memories(db_adapter)
    user_id, original_memories = await _create_test_memories(memory_repo, db_adapter, count=2)

    # Create backup with 2 memories
    backup_service = BackupService(database_type="Postgres")
    backup_path = await backup_service.create_backup()

    try:
        # Add more data after backup
        for i in range(3):
            await memory_repo.create_memory(
                user_id=user_id,
                memory=MemoryCreate(
                    title=f"Post-backup Memory {i}",
                    content=f"This was added after the backup",
                    context=f"Post-backup context {i}",
                    keywords=["post-backup"],
                    tags=["post-backup"],
                    importance=5,
                ),
            )

        # Verify 5 total memories now
        async with db_adapter.system_session() as session:
            result = await session.execute(text("SELECT count(*) FROM memories"))
            assert result.scalar() == 5

        # Restore backup — recycles pool to avoid stale cached statements
        await _restore_and_recycle_pool(backup_service, backup_path, db_adapter)

        # Verify restored to 2 memories (fresh connection avoids OID cache issues)
        count = await _fresh_query(db_adapter, "SELECT count(*) FROM memories")
        assert count == 2

    finally:
        backup_path.unlink(missing_ok=True)
