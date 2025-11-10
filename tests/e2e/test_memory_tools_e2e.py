"""
End-to-end tests for MCP memory tools via HTTP

Requires:
- PostgreSQL with pgvector running in Docker
- MCP server running on configured port
- FastEmbed embeddings adapter

Tests the complete stack: HTTP → FastMCP Client → MCP Protocol → Service → Repository → PostgreSQL + Embeddings
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_memory_basic_e2e(docker_services, mcp_server_url):
    """Test basic memory creation with real embeddings and database"""
    async with Client(mcp_server_url) as client:
        # Create memory via MCP tool
        result = await client.call_tool("create_memory", {
            "title": "Python AsyncIO E2E Test",
            "content": "AsyncIO enables concurrent I/O operations in Python using async/await syntax",
            "context": "Testing memory creation in E2E environment with real database",
            "keywords": ["python", "asyncio", "testing"],
            "tags": ["testing", "python"],
            "importance": 8
        })

        # Validate response structure
        assert result.data is not None
        assert result.data.id is not None
        assert result.data.title == "Python AsyncIO E2E Test"
        assert isinstance(result.data.linked_memory_ids, list)
        assert isinstance(result.data.similar_memories, list)
        assert isinstance(result.data.project_ids, list)
        assert isinstance(result.data.code_artifact_ids, list)
        assert isinstance(result.data.document_ids, list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_memory_auto_linking_e2e(docker_services, mcp_server_url):
    """Test that create_memory auto-links to similar memories via embeddings"""
    async with Client(mcp_server_url) as client:
        # Create first memory about Docker
        result1 = await client.call_tool("create_memory", {
            "title": "Docker Container Basics",
            "content": "Docker containers provide isolated environments for applications",
            "context": "Testing auto-linking behavior in E2E",
            "keywords": ["docker", "containers", "devops"],
            "tags": ["docker", "infrastructure"],
            "importance": 7
        })

        assert result1.data is not None
        memory1_id = result1.data.id

        # Create second memory also about Docker - should auto-link
        result2 = await client.call_tool("create_memory", {
            "title": "Docker Networking",
            "content": "Docker provides networking capabilities to connect containers",
            "context": "Testing auto-linking with semantic similarity",
            "keywords": ["docker", "networking", "containers"],
            "tags": ["docker", "networking"],
            "importance": 7
        })

        assert result2.data is not None

        # Second memory should have auto-linked to first (similar keywords)
        assert len(result2.data.similar_memories) > 0
        similar_ids = [m.id for m in result2.data.similar_memories]
        assert memory1_id in similar_ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_query_memory_e2e(docker_services, mcp_server_url):
    """Test semantic memory search with real pgvector"""
    async with Client(mcp_server_url) as client:
        # Create a memory about testing
        create_result = await client.call_tool("create_memory", {
            "title": "Python Testing Best Practices",
            "content": "Use pytest for testing Python applications with fixtures and parametrization",
            "context": "Testing semantic search in E2E environment",
            "keywords": ["python", "pytest", "testing"],
            "tags": ["testing", "best-practices"],
            "importance": 8
        })

        assert create_result.data is not None

        # Query for the memory
        query_result = await client.call_tool("query_memory", {
            "query": "python testing practices",
            "query_context": "looking for testing information",
            "k": 5,
            "include_links": False
        })

        # Validate query response structure
        assert query_result.data is not None
        assert query_result.data.query == "python testing practices"
        assert isinstance(query_result.data.primary_memories, list)
        assert isinstance(query_result.data.linked_memories, list)
        assert query_result.data.total_count > 0
        assert query_result.data.token_count > 0
        assert isinstance(query_result.data.truncated, bool)

        # Should find the memory we just created
        found_titles = [m.title for m in query_result.data.primary_memories]
        assert "Python Testing Best Practices" in found_titles


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_and_query_persistence_e2e(docker_services, mcp_server_url):
    """Test that memories persist in database and can be queried"""
    async with Client(mcp_server_url) as client:
        # Create memory with unique title
        unique_title = "FastAPI Development Patterns E2E"
        create_result = await client.call_tool("create_memory", {
            "title": unique_title,
            "content": "FastAPI is a modern Python web framework with automatic API documentation",
            "context": "Testing database persistence across operations",
            "keywords": ["fastapi", "python", "web"],
            "tags": ["framework", "python"],
            "importance": 7
        })

        assert create_result.data is not None
        created_id = create_result.data.id

        # Query to verify persistence
        query_result = await client.call_tool("query_memory", {
            "query": "FastAPI web framework",
            "query_context": "verifying persistence of created memory",
            "k": 10,
            "include_links": False
        })

        assert query_result.data is not None

        # Memory should be found in query results
        found_memory = None
        for memory in query_result.data.primary_memories:
            if memory.id == created_id:
                found_memory = memory
                break

        assert found_memory is not None
        assert found_memory.title == unique_title
        assert found_memory.importance == 7


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_query_memory_with_linked_memories_e2e(docker_services, mcp_server_url):
    """Test query with include_links to retrieve 1-hop neighbor memories"""
    async with Client(mcp_server_url) as client:
        # Create two related memories that will auto-link
        result1 = await client.call_tool("create_memory", {
            "title": "PostgreSQL Database",
            "content": "PostgreSQL is a powerful open-source relational database",
            "context": "Testing linked memory retrieval",
            "keywords": ["postgresql", "database", "sql"],
            "tags": ["database"],
            "importance": 8
        })
        
        assert result1.data is not None

        result2 = await client.call_tool("create_memory", {
            "title": "PostgreSQL Indexing",
            "content": "PostgreSQL supports various index types including B-tree and GIN",
            "context": "Testing linked memory retrieval with auto-linking",
            "keywords": ["postgresql", "indexing", "performance"],
            "tags": ["database", "performance"],
            "importance": 7
        })

        # These should have auto-linked due to keyword overlap
        assert len(result2.data.similar_memories) > 0

        # Query with include_links enabled
        query_result = await client.call_tool("query_memory", {
            "query": "postgresql database",
            "query_context": "testing linked memory retrieval",
            "k": 5,
            "include_links": True,
            "max_links_per_primary": 5
        })

        assert query_result.data is not None

        # Should have primary memories
        assert len(query_result.data.primary_memories) > 0

        # May have linked memories if relationships exist
        assert isinstance(query_result.data.linked_memories, list)

        # Verify total count includes both primary and linked
        total = len(query_result.data.primary_memories) + len(query_result.data.linked_memories)
        assert query_result.data.total_count == total


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_single_field_e2e(docker_services, mcp_server_url):
    """Test updating a single field preserves other fields (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create memory with initial values
        create_result = await client.call_tool("create_memory", {
            "title": "Original Title",
            "content": "Original content about Python asyncio",
            "context": "Original context for testing",
            "keywords": ["python", "asyncio", "original"],
            "tags": ["test", "original"],
            "importance": 7
        })

        assert create_result.data is not None
        memory_id = create_result.data.id

        # Update only the title field
        update_result = await client.call_tool("update_memory", {
            "memory_id": memory_id,
            "title": "Updated Title"
        })

        # Verify: title changed, all other fields unchanged
        assert update_result.data is not None
        assert update_result.data.id == memory_id
        assert update_result.data.title == "Updated Title"
        assert update_result.data.content == "Original content about Python asyncio"
        assert update_result.data.context == "Original context for testing"
        assert update_result.data.keywords == ["python", "asyncio", "original"]
        assert update_result.data.tags == ["test", "original"]
        assert update_result.data.importance == 7


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_multiple_fields_e2e(docker_services, mcp_server_url):
    """Test updating multiple fields simultaneously (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create memory
        create_result = await client.call_tool("create_memory", {
            "title": "Original Multi-Field Title",
            "content": "Original content for multi-field test",
            "context": "Original context",
            "keywords": ["original"],
            "tags": ["test"],
            "importance": 6
        })

        assert create_result.data is not None
        memory_id = create_result.data.id

        # Update title, content, and importance simultaneously
        update_result = await client.call_tool("update_memory", {
            "memory_id": memory_id,
            "title": "Updated Multi-Field Title",
            "content": "Updated content for multi-field test",
            "importance": 9
        })

        # Verify: updated fields changed, others unchanged
        assert update_result.data is not None
        assert update_result.data.title == "Updated Multi-Field Title"
        assert update_result.data.content == "Updated content for multi-field test"
        assert update_result.data.importance == 9
        assert update_result.data.context == "Original context"
        assert update_result.data.keywords == ["original"]
        assert update_result.data.tags == ["test"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_content_triggers_embedding_refresh_e2e(docker_services, mcp_server_url):
    """Test that updating content regenerates embeddings for semantic search"""
    async with Client(mcp_server_url) as client:
        # Create memory about Python
        create_result = await client.call_tool("create_memory", {
            "title": "Async Programming Patterns",
            "content": "Python asyncio enables concurrent I/O operations with async/await syntax",
            "context": "Testing embedding refresh on content update",
            "keywords": ["python", "asyncio"],
            "tags": ["programming"],
            "importance": 8
        })

        assert create_result.data is not None
        memory_id = create_result.data.id

        # Update content to completely different topic (Rust)
        update_result = await client.call_tool("update_memory", {
            "memory_id": memory_id,
            "content": "Rust async enables concurrent operations using futures and tokio runtime"
        })

        assert update_result.data is not None

        # Query for Rust-related content - should find the updated memory
        query_result = await client.call_tool("query_memory", {
            "query": "Rust async programming",
            "query_context": "testing embedding refresh after content update",
            "k": 10,
            "include_links": False
        })

        # Verify: updated memory is found via semantic search
        assert query_result.data is not None
        found_ids = [m.id for m in query_result.data.primary_memories]
        assert memory_id in found_ids, "Updated memory should be found by semantic search for new content"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_persistence_e2e(docker_services, mcp_server_url):
    """Test that memory updates persist to database"""
    async with Client(mcp_server_url) as client:
        # Create memory
        create_result = await client.call_tool("create_memory", {
            "title": "Persistence Test Original",
            "content": "Testing database persistence of updates",
            "context": "E2E persistence validation",
            "keywords": ["persistence", "database"],
            "tags": ["test"],
            "importance": 7
        })

        assert create_result.data is not None
        memory_id = create_result.data.id

        # Update title and importance
        update_result = await client.call_tool("update_memory", {
            "memory_id": memory_id,
            "title": "Persistence Test Updated",
            "importance": 9
        })

        assert update_result.data is not None

        # Query by new title to verify persistence
        query_result = await client.call_tool("query_memory", {
            "query": "Persistence Test Updated",
            "query_context": "verifying update persistence",
            "k": 5,
            "include_links": False
        })

        # Find the updated memory
        found_memory = None
        for memory in query_result.data.primary_memories:
            if memory.id == memory_id:
                found_memory = memory
                break

        # Verify: changes persisted
        assert found_memory is not None, "Updated memory should be found in database"
        assert found_memory.title == "Persistence Test Updated"
        assert found_memory.importance == 9


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_keywords_tags_replacement_e2e(docker_services, mcp_server_url):
    """Test that updating keywords/tags replaces (not appends) existing values"""
    async with Client(mcp_server_url) as client:
        # Create memory with initial keywords and tags
        create_result = await client.call_tool("create_memory", {
            "title": "Keywords Tags Replacement Test",
            "content": "Testing REPLACE semantics for list fields",
            "context": "Validating list field behavior",
            "keywords": ["python", "testing", "original"],
            "tags": ["test", "automation", "original"],
            "importance": 7
        })

        assert create_result.data is not None
        memory_id = create_result.data.id

        # Update keywords and tags to completely different values
        update_result = await client.call_tool("update_memory", {
            "memory_id": memory_id,
            "keywords": ["javascript", "unit-test", "jest"],
            "tags": ["ci", "jest", "integration"]
        })

        # Verify: old values completely replaced, not appended
        assert update_result.data is not None
        assert update_result.data.keywords == ["javascript", "unit-test", "jest"]
        assert update_result.data.tags == ["ci", "jest", "integration"]

        # Verify old keywords/tags are NOT present
        assert "python" not in update_result.data.keywords
        assert "original" not in update_result.data.keywords
        assert "automation" not in update_result.data.tags


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when updating non-existent memory"""
    async with Client(mcp_server_url) as client:
        # Attempt to update a memory that doesn't exist
        try:
            await client.call_tool("update_memory", {
                "memory_id": 999999,
                "title": "This Should Fail"
            })
            # Should not reach here
            assert False, "Expected ToolError for invalid memory_id"
        except Exception as e:
            # Verify error message indicates memory not found
            error_message = str(e)
            assert "not found" in error_message.lower() or "validation_error" in error_message.lower()
