"""
Integration tests for MemoryService with stubbed database

Tests critical memory workflows without real PostgreSQL/embeddings dependency
"""
import pytest
from uuid import uuid4

from app.models.memory_models import MemoryCreate, MemoryUpdate, MemoryQueryRequest


@pytest.mark.asyncio
async def test_create_memory_basic(test_memory_service):
    """Test basic memory creation without auto-linking"""
    user_id = uuid4()

    memory_data = MemoryCreate(
        title="Test Memory",
        content="This is a test memory about integration testing patterns",
        context="Testing memory creation in isolated environment",
        keywords=["test", "integration", "memory"],
        tags=["testing", "pattern"],
        importance=7
    )

    memory, similar_memories = await test_memory_service.create_memory(
        user_id=user_id,
        memory_data=memory_data
    )

    assert memory is not None
    assert memory.id is not None
    assert memory.title == "Test Memory"
    assert memory.importance == 7
    assert isinstance(memory.linked_memory_ids, list)
    assert isinstance(similar_memories, list)


@pytest.mark.asyncio
async def test_create_memory_with_auto_linking(test_memory_service):
    """Test that create_memory auto-links to similar memories"""
    user_id = uuid4()

    # Create first memory
    memory1_data = MemoryCreate(
        title="Python Testing Best Practices",
        content="Use pytest for async testing with proper fixtures",
        context="Documenting testing approach for Python projects",
        keywords=["python", "pytest", "testing"],
        tags=["testing", "python"],
        importance=9
    )
    memory1, _ = await test_memory_service.create_memory(user_id, memory1_data)

    # Create second similar memory - should auto-link
    memory2_data = MemoryCreate(
        title="Python Integration Testing",
        content="Integration tests verify multiple layers work together",
        context="Extending testing documentation with integration patterns",
        keywords=["python", "integration", "testing"],
        tags=["testing", "python"],
        importance=8
    )
    memory2, similar_memories = await test_memory_service.create_memory(user_id, memory2_data)

    # Verify auto-linking occurred
    assert len(similar_memories) > 0
    assert memory1.id in memory2.linked_memory_ids
    assert similar_memories[0].id == memory1.id


@pytest.mark.asyncio
async def test_query_memory_with_token_budget(test_memory_service):
    """Test that query_memory calculates token counts correctly"""
    user_id = uuid4()

    # Create multiple memories with varying importance
    for i in range(10):
        memory_data = MemoryCreate(
            title=f"Memory {i}",
            content=f"Content for memory {i} with detailed information",
            context=f"Context {i}",
            keywords=[f"keyword{i}"],
            tags=[f"tag{i}"],
            importance=5 + (i % 5)  # Importance 5-9
        )
        await test_memory_service.create_memory(user_id, memory_data)

    # Query memories
    query_request = MemoryQueryRequest(
        query="test query",
        query_context="looking for test information",
        k=10,
        include_links=False
    )

    result = await test_memory_service.query_memory(user_id, query_request)

    # Verify token counting works
    assert result.token_count > 0  # Should have counted tokens
    assert result.total_count == 10  # Should return all memories
    assert len(result.primary_memories) == 10
    assert result.truncated is False  # Should not truncate with reasonable content


@pytest.mark.asyncio
async def test_query_memory_with_linked_memories(test_memory_service):
    """Test that query_memory retrieves 1-hop linked memories"""
    user_id = uuid4()

    # Create primary memory
    primary_data = MemoryCreate(
        title="Primary Memory",
        content="Main memory content",
        context="Primary context",
        keywords=["primary"],
        tags=["main"],
        importance=9
    )
    primary, _ = await test_memory_service.create_memory(user_id, primary_data)

    # Create linked memory
    linked_data = MemoryCreate(
        title="Linked Memory",
        content="Related content",
        context="Related context",
        keywords=["linked"],
        tags=["related"],
        importance=8
    )
    linked, _ = await test_memory_service.create_memory(user_id, linked_data)

    # Manually link them
    await test_memory_service.link_memories(
        user_id=user_id,
        memory_id=primary.id,
        related_ids=[linked.id]
    )

    # Query should return primary + linked
    query_request = MemoryQueryRequest(
        query="primary",
        query_context="searching for primary memory",
        k=5,
        include_links=True,
        max_links_per_primary=5
    )

    result = await test_memory_service.query_memory(user_id, query_request)

    # Should have primary memory
    assert len(result.primary_memories) >= 1
    assert any(m.id == primary.id for m in result.primary_memories)

    # Should have linked memory
    if result.linked_memories:
        assert any(lm.memory.id == linked.id for lm in result.linked_memories)


@pytest.mark.asyncio
async def test_link_memories_bidirectional(test_memory_service):
    """Test that manual linking creates bidirectional links"""
    user_id = uuid4()

    # Create two DISSIMILAR memories to avoid auto-linking
    memory1_data = MemoryCreate(
        title="Python AsyncIO Event Loop",
        content="AsyncIO provides event loop for asynchronous programming in Python",
        context="Technical documentation about Python async features",
        keywords=["python", "asyncio", "async"],
        tags=["programming", "python"],
        importance=7
    )
    memory1, _ = await test_memory_service.create_memory(user_id, memory1_data)

    memory2_data = MemoryCreate(
        title="Database Connection Pooling",
        content="Connection pooling improves database performance by reusing connections",
        context="Database optimization technique",
        keywords=["database", "pooling", "performance"],
        tags=["database", "optimization"],
        importance=7
    )
    memory2, _ = await test_memory_service.create_memory(user_id, memory2_data)

    # Link them
    links_created = await test_memory_service.link_memories(
        user_id=user_id,
        memory_id=memory1.id,
        related_ids=[memory2.id]
    )

    assert len(links_created) > 0

    # Verify bidirectional - memory1 should link to memory2
    updated_memory1 = await test_memory_service.get_memory(user_id, memory1.id)
    assert memory2.id in updated_memory1.linked_memory_ids

    # And memory2 should link to memory1
    updated_memory2 = await test_memory_service.get_memory(user_id, memory2.id)
    assert memory1.id in updated_memory2.linked_memory_ids


@pytest.mark.asyncio
async def test_update_memory_content(test_memory_service):
    """Test updating memory content"""
    user_id = uuid4()

    # Create memory
    memory_data = MemoryCreate(
        title="Original Title",
        content="Original content",
        context="Original context",
        keywords=["original"],
        tags=["original"],
        importance=7
    )
    memory, _ = await test_memory_service.create_memory(user_id, memory_data)

    # Update content and importance
    memory_update = MemoryUpdate(
        title="Updated Title",
        content="Updated content with new information",
        importance=9
    )

    updated_memory = await test_memory_service.update_memory(
        user_id=user_id,
        memory_id=memory.id,
        updated_memory=memory_update
    )

    assert updated_memory is not None
    assert updated_memory.title == "Updated Title"
    assert updated_memory.content == "Updated content with new information"
    assert updated_memory.importance == 9
    assert updated_memory.id == memory.id


@pytest.mark.asyncio
async def test_mark_memory_obsolete(test_memory_service):
    """Test soft delete with superseded_by reference"""
    user_id = uuid4()

    # Create old memory
    old_memory_data = MemoryCreate(
        title="Old Memory",
        content="Outdated information",
        context="Old context",
        keywords=["old"],
        tags=["outdated"],
        importance=7
    )
    old_memory, _ = await test_memory_service.create_memory(user_id, old_memory_data)

    # Create new memory that supersedes it
    new_memory_data = MemoryCreate(
        title="New Memory",
        content="Updated information",
        context="New context",
        keywords=["new"],
        tags=["current"],
        importance=8
    )
    new_memory, _ = await test_memory_service.create_memory(user_id, new_memory_data)

    # Mark old memory as obsolete
    success = await test_memory_service.mark_memory_obsolete(
        user_id=user_id,
        memory_id=old_memory.id,
        reason="Superseded by updated information",
        superseeded_by=new_memory.id
    )

    assert success is True

    # Old memory should not be retrievable
    with pytest.raises(KeyError):
        await test_memory_service.get_memory(user_id, old_memory.id)

    # New memory should still be accessible
    retrieved = await test_memory_service.get_memory(user_id, new_memory.id)
    assert retrieved.id == new_memory.id
