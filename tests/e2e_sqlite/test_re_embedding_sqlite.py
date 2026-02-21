"""
E2E tests for re-embedding with real in-memory SQLite and real embedding adapters.

Tests the full stack: ReEmbeddingService -> SqliteMemoryRepository -> sqlite-vec
"""
import pytest
from uuid import uuid4

from sqlalchemy import text

from app.config.settings import settings
from app.repositories.sqlite.sqlite_adapter import SqliteDatabaseAdapter
from app.repositories.sqlite.memory_repository import SqliteMemoryRepository
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter
from app.services.re_embedding_service import ReEmbeddingService
from app.models.memory_models import MemoryCreate


@pytest.fixture(scope="module")
def embedding_adapter():
    """Module-scoped embedding adapter (expensive to load).

    Forces FastEmbed-compatible model regardless of env config (e.g. docker/.env
    may set EMBEDDING_MODEL to an OpenAI model).
    """
    original_model = settings.EMBEDDING_MODEL
    original_dims = settings.EMBEDDING_DIMENSIONS
    settings.EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
    settings.EMBEDDING_DIMENSIONS = 384
    try:
        return FastEmbeddingAdapter()
    finally:
        settings.EMBEDDING_MODEL = original_model
        settings.EMBEDDING_DIMENSIONS = original_dims


@pytest.fixture
async def sqlite_repo(embedding_adapter):
    """Create a fresh in-memory SQLite repo for each test"""
    original_sqlite_memory = settings.SQLITE_MEMORY
    original_database = settings.DATABASE
    original_model = settings.EMBEDDING_MODEL
    original_dims = settings.EMBEDDING_DIMENSIONS

    settings.DATABASE = "SQLite"
    settings.SQLITE_MEMORY = True
    settings.EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
    settings.EMBEDDING_DIMENSIONS = 384

    try:
        db_adapter = SqliteDatabaseAdapter()
        await db_adapter.init_db()

        repo = SqliteMemoryRepository(
            db_adapter=db_adapter,
            embedding_adapter=embedding_adapter,
            rerank_adapter=None,
        )

        yield repo, db_adapter

        import asyncio
        await asyncio.sleep(0.05)
        try:
            await db_adapter.dispose()
        except (RuntimeError, Exception):
            pass
    finally:
        settings.DATABASE = original_database
        settings.SQLITE_MEMORY = original_sqlite_memory
        settings.EMBEDDING_MODEL = original_model
        settings.EMBEDDING_DIMENSIONS = original_dims


async def _create_user(db_adapter, user_id):
    """Create a user row in the database (required for FK constraints)"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
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


async def _create_test_memories(repo, db_adapter, count=5):
    """Helper to create test memories via the repository"""
    user_id = uuid4()
    await _create_user(db_adapter, user_id)

    memories = []
    for i in range(count):
        memory = await repo.create_memory(
            user_id=user_id,
            memory=MemoryCreate(
                title=f"Test Memory {i}",
                content=f"This is test memory content number {i} about topic {i}",
                context=f"Testing context for memory {i}",
                keywords=[f"keyword{i}", "test"],
                tags=[f"tag{i}", "test"],
                importance=7,
            ),
        )
        memories.append(memory)
    return user_id, memories


@pytest.mark.asyncio
async def test_re_embed_search_works_after(sqlite_repo, embedding_adapter):
    """Create memories, re-embed, run semantic search, verify results returned"""
    repo, db_adapter = sqlite_repo
    user_id, memories = await _create_test_memories(repo, db_adapter, count=3)

    # Re-embed all memories
    service = ReEmbeddingService(
        memory_repository=repo,
        embedding_adapter=embedding_adapter,
        batch_size=10,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 3
    assert result.validation.all_passed

    # Verify search works after re-embedding
    search_results = await repo.search(
        user_id=user_id,
        query="test memory content",
        query_context="verifying search after re-embed",
        k=3,
        importance_threshold=None,
        project_ids=None,
        exclude_ids=None,
    )
    assert len(search_results) > 0


@pytest.mark.asyncio
async def test_re_embed_count_integrity(sqlite_repo, embedding_adapter):
    """After re-embed, verify vec_memories row count == memories row count"""
    repo, db_adapter = sqlite_repo
    user_id, memories = await _create_test_memories(repo, db_adapter, count=5)

    service = ReEmbeddingService(
        memory_repository=repo,
        embedding_adapter=embedding_adapter,
        batch_size=3,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 5
    assert result.validation.count_ok


@pytest.mark.asyncio
async def test_re_embed_preserves_memory_data(sqlite_repo, embedding_adapter):
    """After re-embed, verify all memory fields (title, content, tags, etc.) unchanged"""
    repo, db_adapter = sqlite_repo
    user_id, original_memories = await _create_test_memories(repo, db_adapter, count=3)

    service = ReEmbeddingService(
        memory_repository=repo,
        embedding_adapter=embedding_adapter,
        batch_size=10,
    )
    await service.re_embed_all()

    # Re-read all memories and verify data unchanged
    for original in original_memories:
        refreshed = await repo.get_memory_by_id(user_id=user_id, memory_id=original.id)
        assert refreshed.title == original.title
        assert refreshed.content == original.content
        assert refreshed.context == original.context
        assert refreshed.keywords == original.keywords
        assert refreshed.tags == original.tags
        assert refreshed.importance == original.importance


@pytest.mark.asyncio
async def test_re_embed_empty_database(sqlite_repo, embedding_adapter):
    """Re-embedding an empty database should succeed with no work done"""
    repo, db_adapter = sqlite_repo

    service = ReEmbeddingService(
        memory_repository=repo,
        embedding_adapter=embedding_adapter,
        batch_size=10,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 0
    assert result.total_memories == 0
    assert result.validation.all_passed


@pytest.mark.asyncio
async def test_re_embed_validation_checks(sqlite_repo, embedding_adapter):
    """Verify all validation checks pass after successful re-embed"""
    repo, db_adapter = sqlite_repo
    user_id, memories = await _create_test_memories(repo, db_adapter, count=4)

    service = ReEmbeddingService(
        memory_repository=repo,
        embedding_adapter=embedding_adapter,
        batch_size=2,
    )
    result = await service.re_embed_all()

    assert result.validation.count_ok
    assert result.validation.dimensions_ok
    assert result.validation.search_ok
    assert result.validation.all_passed
