"""
E2E tests for re-embedding with real PostgreSQL and real embedding adapters.

Tests the full stack: ReEmbeddingService -> PostgresMemoryRepository -> pgvector
"""
import pytest
import pytest_asyncio
from uuid import uuid4

from sqlalchemy import text

from app.config.settings import settings
from app.repositories.embeddings.embedding_adapter import FastEmbeddingAdapter
from app.repositories.postgres.memory_repository import PostgresMemoryRepository
from app.services.re_embedding_service import ReEmbeddingService
from app.models.memory_models import MemoryCreate

pytestmark = pytest.mark.asyncio(loop_scope="session")

FASTEMBED_DIMENSIONS = 384


@pytest.fixture(scope="module")
def fastembed_adapter():
    """Module-scoped FastEmbed adapter — avoids dependency on external API providers."""
    return FastEmbeddingAdapter()


@pytest_asyncio.fixture(loop_scope="session")
async def postgres_repo(db_adapter, fastembed_adapter):
    """Create a PostgresMemoryRepository wired to the session-scoped DB and FastEmbed.

    Also resizes the pgvector embedding column to match FastEmbed's 384 dimensions,
    since the DB may have been migrated with a different dimension (e.g. 1536 for OpenAI).
    """
    original_dims = settings.EMBEDDING_DIMENSIONS
    settings.EMBEDDING_DIMENSIONS = FASTEMBED_DIMENSIONS

    repo = PostgresMemoryRepository(
        db_adapter=db_adapter,
        embedding_adapter=fastembed_adapter,
        rerank_adapter=None,
    )

    # Resize the embedding column to match FastEmbed output
    await repo.reset_embedding_storage()

    yield repo

    settings.EMBEDDING_DIMENSIONS = original_dims


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


async def _create_test_memories(repo, db_adapter, count=5):
    """Helper to create test memories via the repository."""
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


async def _truncate_memories(db_adapter):
    """Truncate memories table for test isolation."""
    async with db_adapter.system_session() as session:
        await session.execute(text("TRUNCATE memories CASCADE"))


@pytest.mark.e2e
async def test_re_embed_search_works_after(postgres_repo, db_adapter, fastembed_adapter):
    """Create memories, re-embed, run semantic search, verify results returned."""
    await _truncate_memories(db_adapter)
    user_id, memories = await _create_test_memories(postgres_repo, db_adapter, count=3)

    service = ReEmbeddingService(
        memory_repository=postgres_repo,
        embedding_adapter=fastembed_adapter,
        batch_size=10,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 3
    assert result.validation.all_passed

    search_results = await postgres_repo.search(
        user_id=user_id,
        query="test memory content",
        query_context="verifying search after re-embed",
        k=3,
        importance_threshold=None,
        project_ids=None,
        exclude_ids=None,
    )
    assert len(search_results) > 0


@pytest.mark.e2e
async def test_re_embed_count_integrity(postgres_repo, db_adapter, fastembed_adapter):
    """After re-embed, verify embedding count matches memory count."""
    await _truncate_memories(db_adapter)
    user_id, memories = await _create_test_memories(postgres_repo, db_adapter, count=5)

    service = ReEmbeddingService(
        memory_repository=postgres_repo,
        embedding_adapter=fastembed_adapter,
        batch_size=3,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 5
    assert result.validation.count_ok


@pytest.mark.e2e
async def test_re_embed_preserves_memory_data(postgres_repo, db_adapter, fastembed_adapter):
    """After re-embed, verify all memory fields unchanged."""
    await _truncate_memories(db_adapter)
    user_id, original_memories = await _create_test_memories(postgres_repo, db_adapter, count=3)

    service = ReEmbeddingService(
        memory_repository=postgres_repo,
        embedding_adapter=fastembed_adapter,
        batch_size=10,
    )
    await service.re_embed_all()

    for original in original_memories:
        refreshed = await postgres_repo.get_memory_by_id(user_id=user_id, memory_id=original.id)
        assert refreshed.title == original.title
        assert refreshed.content == original.content
        assert refreshed.context == original.context
        assert refreshed.keywords == original.keywords
        assert refreshed.tags == original.tags
        assert refreshed.importance == original.importance


@pytest.mark.e2e
async def test_re_embed_empty_database(postgres_repo, db_adapter, fastembed_adapter):
    """Re-embedding an empty database should succeed with no work done."""
    await _truncate_memories(db_adapter)

    service = ReEmbeddingService(
        memory_repository=postgres_repo,
        embedding_adapter=fastembed_adapter,
        batch_size=10,
    )
    result = await service.re_embed_all()

    assert result.total_processed == 0
    assert result.total_memories == 0
    assert result.validation.all_passed


@pytest.mark.e2e
async def test_re_embed_validation_checks(postgres_repo, db_adapter, fastembed_adapter):
    """Verify all validation checks pass after successful re-embed."""
    await _truncate_memories(db_adapter)
    user_id, memories = await _create_test_memories(postgres_repo, db_adapter, count=4)

    service = ReEmbeddingService(
        memory_repository=postgres_repo,
        embedding_adapter=fastembed_adapter,
        batch_size=2,
    )
    result = await service.re_embed_all()

    assert result.validation.count_ok
    assert result.validation.dimensions_ok
    assert result.validation.search_ok
    assert result.validation.all_passed
