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
        memory2_id = result2.data.id

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
