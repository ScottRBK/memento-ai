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
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Python AsyncIO E2E Test', 'content':
            'AsyncIO enables concurrent I/O operations in Python using async/await syntax'
            , 'context':
            'Testing memory creation in E2E environment with real database',
            'keywords': ['python', 'asyncio', 'testing'], 'tags': [
            'testing', 'python'], 'importance': 8}})
        assert result.data is not None
        assert result.data["id"] is not None
        assert result.data["title"] == 'Python AsyncIO E2E Test'
        assert isinstance(result.data["linked_memory_ids"], list)
        assert isinstance(result.data["similar_memories"], list)
        assert isinstance(result.data["project_ids"], list)
        assert isinstance(result.data["code_artifact_ids"], list)
        assert isinstance(result.data["document_ids"], list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_memory_auto_linking_e2e(docker_services, mcp_server_url):
    """Test that create_memory auto-links to similar memories via embeddings"""
    async with Client(mcp_server_url) as client:
        result1 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Docker Container Basics', 'content':
            'Docker containers provide isolated environments for applications',
            'context': 'Testing auto-linking behavior in E2E', 'keywords':
            ['docker', 'containers', 'devops'], 'tags': ['docker',
            'infrastructure'], 'importance': 7}})
        assert result1.data is not None
        memory1_id = result1.data["id"]
        result2 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Docker Networking', 'content':
            'Docker provides networking capabilities to connect containers',
            'context': 'Testing auto-linking with semantic similarity',
            'keywords': ['docker', 'networking', 'containers'], 'tags': [
            'docker', 'networking'], 'importance': 7}})
        assert result2.data is not None
        assert len(result2.data["similar_memories"]) > 0
        similar_ids = [m["id"] for m in result2.data["similar_memories"]]
        assert memory1_id in similar_ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_query_memory_e2e(docker_services, mcp_server_url):
    """Test semantic memory search with real pgvector"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Python Testing Best Practices', 'content':
            'Use pytest for testing Python applications with fixtures and parametrization'
            , 'context': 'Testing semantic search in E2E environment',
            'keywords': ['python', 'pytest', 'testing'], 'tags': ['testing',
            'best-practices'], 'importance': 8}})
        assert create_result.data is not None
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'python testing practices', 'query_context':
            'looking for testing information', 'k': 5, 'include_links': False}}
            )
        assert query_result.data is not None
        assert query_result.data["query"] == 'python testing practices'
        assert isinstance(query_result.data["primary_memories"], list)
        assert isinstance(query_result.data["linked_memories"], list)
        assert query_result.data["total_count"] > 0
        assert query_result.data["token_count"] > 0
        assert isinstance(query_result.data["truncated"], bool)
        found_titles = [m["title"] for m in query_result.data["primary_memories"]]
        assert 'Python Testing Best Practices' in found_titles


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_and_query_persistence_e2e(docker_services, mcp_server_url
    ):
    """Test that memories persist in database and can be queried"""
    async with Client(mcp_server_url) as client:
        unique_title = 'FastAPI Development Patterns E2E'
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            unique_title, 'content':
            'FastAPI is a modern Python web framework with automatic API documentation'
            , 'context': 'Testing database persistence across operations',
            'keywords': ['fastapi', 'python', 'web'], 'tags': ['framework',
            'python'], 'importance': 7}})
        assert create_result.data is not None
        created_id = create_result.data["id"]
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'FastAPI web framework', 'query_context':
            'verifying persistence of created memory', 'k': 10,
            'include_links': False}})
        assert query_result.data is not None
        found_memory = None
        for memory in query_result.data["primary_memories"]:
            if memory["id"] == created_id:
                found_memory = memory
                break
        assert found_memory is not None
        assert found_memory["title"] == unique_title
        assert found_memory["importance"] == 7


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_query_memory_with_linked_memories_e2e(docker_services,
    mcp_server_url):
    """Test query with include_links to retrieve 1-hop neighbor memories"""
    async with Client(mcp_server_url) as client:
        result1 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'PostgreSQL Database', 'content':
            'PostgreSQL is a powerful open-source relational database',
            'context': 'Testing linked memory retrieval', 'keywords': [
            'postgresql', 'database', 'sql'], 'tags': ['database'],
            'importance': 8}})
        assert result1.data is not None
        result2 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'PostgreSQL Indexing', 'content':
            'PostgreSQL supports various index types including B-tree and GIN',
            'context': 'Testing linked memory retrieval with auto-linking',
            'keywords': ['postgresql', 'indexing', 'performance'], 'tags':
            ['database', 'performance'], 'importance': 7}})
        assert len(result2.data["similar_memories"]) > 0
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'postgresql database', 'query_context':
            'testing linked memory retrieval', 'k': 5, 'include_links': 
            True, 'max_links_per_primary': 5}})
        assert query_result.data is not None
        assert len(query_result.data["primary_memories"]) > 0
        assert isinstance(query_result.data["linked_memories"], list)
        total = len(query_result.data["primary_memories"]) + len(query_result.
            data["linked_memories"])
        assert query_result.data["total_count"] == total


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_single_field_e2e(docker_services, mcp_server_url):
    """Test updating a single field preserves other fields (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Original Title', 'content':
            'Original content about Python asyncio', 'context':
            'Original context for testing', 'keywords': ['python',
            'asyncio', 'original'], 'tags': ['test', 'original'],
            'importance': 7}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'title': 'Updated Title'}})
        assert update_result.data is not None
        assert update_result.data["id"] == memory_id
        assert update_result.data["title"] == 'Updated Title'
        assert update_result.data["content"] == 'Original content about Python asyncio'
        assert update_result.data["context"] == 'Original context for testing'
        assert update_result.data["keywords"] == ['python', 'asyncio', 'original']
        assert update_result.data["tags"] == ['test', 'original']
        assert update_result.data["importance"] == 7


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_multiple_fields_e2e(docker_services,
    mcp_server_url):
    """Test updating multiple fields simultaneously (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Original Multi-Field Title', 'content':
            'Original content for multi-field test', 'context':
            'Original context', 'keywords': ['original'], 'tags': ['test'],
            'importance': 6}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'title': 'Updated Multi-Field Title', 'content':
            'Updated content for multi-field test', 'importance': 9}})
        assert update_result.data is not None
        assert update_result.data["title"] == 'Updated Multi-Field Title'
        assert update_result.data["content"] == 'Updated content for multi-field test'
        assert update_result.data["importance"] == 9
        assert update_result.data["context"] == 'Original context'
        assert update_result.data["keywords"] == ['original']
        assert update_result.data["tags"] == ['test']


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_content_triggers_embedding_refresh_e2e(
    docker_services, mcp_server_url):
    """Test that updating content regenerates embeddings for semantic search"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Async Programming Patterns', 'content':
            'Python asyncio enables concurrent I/O operations with async/await syntax'
            , 'context': 'Testing embedding refresh on content update',
            'keywords': ['python', 'asyncio'], 'tags': ['programming'],
            'importance': 8}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'content':
            'Rust async enables concurrent operations using futures and tokio runtime'
            }})
        assert update_result.data is not None
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'Rust async programming', 'query_context':
            'testing embedding refresh after content update', 'k': 10,
            'include_links': False}})
        assert query_result.data is not None
        found_ids = [m["id"] for m in query_result.data["primary_memories"]]
        assert memory_id in found_ids, 'Updated memory should be found by semantic search for new content'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_persistence_e2e(docker_services, mcp_server_url):
    """Test that memory updates persist to database"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Persistence Test Original', 'content':
            'Testing database persistence of updates', 'context':
            'E2E persistence validation', 'keywords': ['persistence',
            'database'], 'tags': ['test'], 'importance': 7}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'title': 'Persistence Test Updated', 'importance': 9}})
        assert update_result.data is not None
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'Persistence Test Updated', 'query_context':
            'verifying update persistence', 'k': 5, 'include_links': False}})
        found_memory = None
        for memory in query_result.data["primary_memories"]:
            if memory["id"] == memory_id:
                found_memory = memory
                break
        assert found_memory is not None, 'Updated memory should be found in database'
        assert found_memory["title"] == 'Persistence Test Updated'
        assert found_memory["importance"] == 9


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_keywords_tags_replacement_e2e(docker_services,
    mcp_server_url):
    """Test that updating keywords/tags replaces (not appends) existing values"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Keywords Tags Replacement Test', 'content':
            'Testing REPLACE semantics for list fields', 'context':
            'Validating list field behavior', 'keywords': ['python',
            'testing', 'original'], 'tags': ['test', 'automation',
            'original'], 'importance': 7}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'keywords': ['javascript', 'unit-test', 'jest'],
            'tags': ['ci', 'jest', 'integration']}})
        assert update_result.data is not None
        assert update_result.data["keywords"] == ['javascript', 'unit-test',
            'jest']
        assert update_result.data["tags"] == ['ci', 'jest', 'integration']
        assert 'python' not in update_result.data["keywords"]
        assert 'original' not in update_result.data["keywords"]
        assert 'automation' not in update_result.data["tags"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when updating non-existent memory"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool('execute_forgetful_tool', {'tool_name':
                'update_memory', 'arguments': {'memory_id': 999999, 'title':
                'This Should Fail'}})
            assert False, 'Expected ToolError for invalid memory_id'
        except Exception as e:
            error_message = str(e)
            assert 'not found' in error_message.lower(
                ) or 'validation_error' in error_message.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_memory_basic_retrieval_e2e(docker_services, mcp_server_url):
    """Test basic memory retrieval by ID with get_memory tool"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Get Memory E2E Test', 'content':
            'Testing get_memory retrieval by ID in E2E environment',
            'context': 'Validating get_memory tool functionality',
            'keywords': ['get', 'retrieval', 'testing'], 'tags': ['test',
            'get-memory'], 'importance': 8}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_memory', 'arguments': {'memory_id': memory_id}})
        assert get_result.data is not None
        assert get_result.data["id"] == memory_id
        assert get_result.data["title"] == 'Get Memory E2E Test'
        assert get_result.data["content"] == 'Testing get_memory retrieval by ID in E2E environment'
        assert get_result.data["context"] == 'Validating get_memory tool functionality'
        assert get_result.data["keywords"] == ['get', 'retrieval', 'testing']
        assert get_result.data["tags"] == ['test', 'get-memory']
        assert get_result.data["importance"] == 8
        assert isinstance(get_result.data["linked_memory_ids"], list)
        assert isinstance(get_result.data["project_ids"], list)
        assert isinstance(get_result.data["code_artifact_ids"], list)
        assert isinstance(get_result.data["document_ids"], list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_memory_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when retrieving non-existent memory"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool('execute_forgetful_tool', {'tool_name':
                'get_memory', 'arguments': {'memory_id': 999999}})
            assert False, 'Expected ToolError for invalid memory_id'
        except Exception as e:
            error_message = str(e)
            assert 'not found' in error_message.lower(
                ) or 'validation_error' in error_message.lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mark_memory_obsolete_basic_e2e(docker_services, mcp_server_url):
    """Test basic memory obsolete functionality with mark_memory_obsolete tool"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Memory to Obsolete', 'content':
            'This memory will be marked as obsolete in the test', 'context':
            'Testing mark_memory_obsolete functionality', 'keywords': [
            'obsolete', 'test', 'soft-delete'], 'tags': ['test', 'obsolete'
            ], 'importance': 7}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        obsolete_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'mark_memory_obsolete', 'arguments': {'memory_id':
            memory_id, 'reason': 'Testing soft delete functionality'}})
        assert obsolete_result.data["success"] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mark_memory_obsolete_filtered_from_query_e2e(docker_services,
    mcp_server_url):
    """Test that obsolete memories are filtered from query_memory results"""
    async with Client(mcp_server_url) as client:
        result1 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Kubernetes Basics Active', 'content':
            'Kubernetes orchestrates containerized applications across clusters'
            , 'context': 'Testing obsolete filtering in queries',
            'keywords': ['kubernetes', 'containers', 'orchestration'],
            'tags': ['k8s', 'infrastructure'], 'importance': 8}})
        memory1_id = result1.data["id"]
        result2 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Kubernetes Networking Active', 'content':
            'Kubernetes provides networking capabilities for pod communication'
            , 'context': 'Testing obsolete filtering - this remains active',
            'keywords': ['kubernetes', 'networking', 'pods'], 'tags': [
            'k8s', 'networking'], 'importance': 8}})
        memory2_id = result2.data["id"]
        result3 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Kubernetes Obsolete Memory', 'content':
            'Kubernetes content that will be marked obsolete', 'context':
            'Testing obsolete filtering - this will be obsolete',
            'keywords': ['kubernetes', 'obsolete', 'test'], 'tags': ['k8s',
            'test'], 'importance': 7}})
        memory3_id = result3.data["id"]
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'mark_memory_obsolete', 'arguments': {'memory_id': memory3_id,
            'reason':
            'Testing that obsolete memories are filtered from queries'}})
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'kubernetes containers orchestration', 'query_context':
            'testing obsolete filtering in semantic search', 'k': 10,
            'include_links': False}})
        assert query_result.data is not None
        found_ids = [m["id"] for m in query_result.data["primary_memories"]]
        assert memory1_id in found_ids or memory2_id in found_ids, 'At least one active memory should be found'
        assert memory3_id not in found_ids, 'Obsolete memory should be filtered from query results'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mark_memory_obsolete_retrievable_by_id_e2e(docker_services,
    mcp_server_url):
    """Test that obsolete memories can still be retrieved by ID using get_memory (audit trail)"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Memory for Audit Trail Test', 'content':
            'This memory will be obsolete but retrievable by ID', 'context':
            'Testing soft-delete audit trail behavior', 'keywords': [
            'audit', 'obsolete', 'retrieval'], 'tags': ['test', 'audit'],
            'importance': 7}})
        assert create_result.data is not None
        memory_id = create_result.data["id"]
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'mark_memory_obsolete', 'arguments': {'memory_id': memory_id,
            'reason':
            'Testing that get_memory can still retrieve obsolete memories'}})
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'audit trail obsolete retrieval', 'query_context':
            'verifying obsolete memory filtered from query', 'k': 10,
            'include_links': False}})
        query_ids = [m["id"] for m in query_result.data["primary_memories"]]
        assert memory_id not in query_ids, 'Obsolete memory should not appear in query_memory results'
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_memory', 'arguments': {'memory_id': memory_id}})
        assert get_result.data is not None
        assert get_result.data["id"] == memory_id
        assert get_result.data["title"] == 'Memory for Audit Trail Test'
        assert get_result.data["content"] == 'This memory will be obsolete but retrievable by ID'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_mark_memory_obsolete_with_superseded_by_e2e(docker_services,
    mcp_server_url):
    """Test marking memory obsolete with superseded_by parameter"""
    async with Client(mcp_server_url) as client:
        old_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Old API Pattern', 'content': 'Use REST API with XML responses',
            'context': 'Outdated API pattern that will be superseded',
            'keywords': ['api', 'rest', 'xml'], 'tags': ['api',
            'deprecated'], 'importance': 6}})
        old_memory_id = old_result.data["id"]
        new_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'New API Pattern', 'content':
            'Use REST API with JSON responses', 'context':
            'Modern API pattern superseding XML approach', 'keywords': [
            'api', 'rest', 'json'], 'tags': ['api', 'modern'], 'importance':
            8}})
        new_memory_id = new_result.data["id"]
        obsolete_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'mark_memory_obsolete', 'arguments': {'memory_id':
            old_memory_id, 'reason':
            'Superseded by modern JSON API pattern', 'superseded_by':
            new_memory_id}})
        assert obsolete_result.data["success"] is True
        query_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'query_memory', 'arguments': {'query':
            'REST API pattern', 'query_context':
            'finding current API patterns', 'k': 10, 'include_links': False}})
        found_ids = [m["id"] for m in query_result.data["primary_memories"]]
        assert old_memory_id not in found_ids, 'Old memory should be filtered from queries'
        assert new_memory_id in found_ids or len(found_ids
            ) > 0, 'New memory should be found in queries'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_add_project_ids_e2e(docker_services,
    mcp_server_url):
    """Test adding project_ids to a memory using update_memory tool"""
    async with Client(mcp_server_url) as client:
        project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {'name':
            'update-memory-project-test', 'description':
            'Project for testing memory updates with project_ids',
            'project_type': 'development'}})
        project_id = project_result.data["id"]
        memory_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Memory without project', 'content':
            'This memory will be updated to add a project', 'context':
            'Testing project_ids updates', 'keywords': ['test', 'project',
            'update'], 'tags': ['test'], 'importance': 7}})
        memory_id = memory_result.data["id"]
        assert memory_result.data["project_ids"] == []
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'project_ids': [project_id]}})
        assert update_result.data is not None
        assert project_id in update_result.data["project_ids"]
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_memory', 'arguments': {'memory_id': memory_id}})
        assert project_id in get_result.data["project_ids"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_add_multiple_projects_e2e(docker_services,
    mcp_server_url):
    """Test adding multiple project_ids to a memory"""
    async with Client(mcp_server_url) as client:
        project1_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'create_project', 'arguments': {'name':
            'multi-project-1', 'description':
            'First project for multi-project test', 'project_type':
            'development'}})
        project1_id = project1_result.data["id"]
        project2_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'create_project', 'arguments': {'name':
            'multi-project-2', 'description':
            'Second project for multi-project test', 'project_type': 'work'}})
        project2_id = project2_result.data["id"]
        memory_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Memory for multiple projects', 'content':
            'This memory belongs to multiple projects', 'context':
            'Testing multiple project_ids', 'keywords': ['test',
            'multi-project'], 'tags': ['test'], 'importance': 7}})
        memory_id = memory_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'project_ids': [project1_id, project2_id]}})
        assert update_result.data is not None
        assert project1_id in update_result.data["project_ids"]
        assert project2_id in update_result.data["project_ids"]
        assert len(update_result.data["project_ids"]) == 2


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_memory_remove_project_ids_e2e(docker_services,
    mcp_server_url):
    """Test removing project_ids from a memory"""
    async with Client(mcp_server_url) as client:
        project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {'name':
            'remove-project-test', 'description':
            'Project to be removed from memory', 'project_type':
            'development'}})
        project_id = project_result.data["id"]
        memory_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Memory with project to remove', 'content':
            'This memory will have its project removed', 'context':
            'Testing project_ids removal', 'keywords': ['test', 'remove',
            'project'], 'tags': ['test'], 'importance': 7, 'project_ids': [
            project_id]}})
        memory_id = memory_result.data["id"]
        assert project_id in memory_result.data["project_ids"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_memory', 'arguments': {'memory_id':
            memory_id, 'project_ids': []}})
        assert update_result.data is not None
        assert update_result.data["project_ids"] == []
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_memory', 'arguments': {'memory_id': memory_id}})
        assert get_result.data["project_ids"] == []


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_recent_memories_basic_e2e(docker_services, mcp_server_url):
    """Test getting recent memories sorted by creation timestamp"""
    async with Client(mcp_server_url) as client:
        # Create several memories
        memory_ids = []
        for i in range(5):
            result = await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'create_memory', 'arguments': {
                    'title': f'Recent Memory Test {i}',
                    'content': f'Testing recent memories retrieval {i}',
                    'context': f'E2E test for get_recent_memories {i}',
                    'keywords': ['recent', 'test', f'memory{i}'],
                    'tags': ['test', 'recent'],
                    'importance': 7
                }
            })
            memory_ids.append(result.data["id"])

        # Get recent memories (should return newest first)
        recent_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_recent_memories', 'arguments': {
                'limit': 3
            }
        })

        assert recent_result.content is not None
        import json
        memories = json.loads(recent_result.content[0].text)
        assert isinstance(memories, list)
        assert len(memories) >= 3

        # Check that most recent memories are returned
        recent_ids = [m["id"] for m in memories]
        # The last 3 created memories should be in the results
        assert memory_ids[-1] in recent_ids or memory_ids[-2] in recent_ids or memory_ids[-3] in recent_ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_recent_memories_with_project_filter_e2e(docker_services, mcp_server_url):
    """Test getting recent memories filtered by project"""
    async with Client(mcp_server_url) as client:
        # Create a project
        project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'recent-memories-project-filter-test',
                'description': 'Project for testing get_recent_memories filtering',
                'project_type': 'development'
            }
        })
        project_id = project_result.data["id"]

        # Create memories with and without the project
        with_project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {
                'title': 'Memory With Project',
                'content': 'This memory belongs to the test project',
                'context': 'Testing project filtering in get_recent_memories',
                'keywords': ['project', 'filter', 'test'],
                'tags': ['test'],
                'importance': 7,
                'project_ids': [project_id]
            }
        })
        memory_with_project_id = with_project_result.data["id"]

        without_project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {
                'title': 'Memory Without Project',
                'content': 'This memory does not belong to any project',
                'context': 'Testing project filtering exclusion',
                'keywords': ['no-project', 'test'],
                'tags': ['test'],
                'importance': 7
            }
        })
        memory_without_project_id = without_project_result.data["id"]

        # Get recent memories filtered by project
        recent_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_recent_memories', 'arguments': {
                'limit': 10,
                'project_ids': [project_id]
            }
        })

        assert recent_result.content is not None
        import json
        memories = json.loads(recent_result.content[0].text)
        recent_ids = [m["id"] for m in memories]

        # Should include memory with project
        assert memory_with_project_id in recent_ids
        # Should NOT include memory without project
        assert memory_without_project_id not in recent_ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_recent_memories_excludes_obsolete_e2e(docker_services, mcp_server_url):
    """Test that get_recent_memories excludes obsolete memories"""
    async with Client(mcp_server_url) as client:
        # Create an active memory
        active_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {
                'title': 'Active Memory for Recent Test',
                'content': 'This memory should appear in recent results',
                'context': 'Testing obsolete exclusion',
                'keywords': ['active', 'recent', 'test'],
                'tags': ['test', 'active'],
                'importance': 7
            }
        })
        active_memory_id = active_result.data["id"]

        # Create a memory to be marked obsolete
        obsolete_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {
                'title': 'Memory To Be Obsolete',
                'content': 'This memory will be marked obsolete',
                'context': 'Testing obsolete filtering',
                'keywords': ['obsolete', 'test'],
                'tags': ['test', 'obsolete'],
                'importance': 7
            }
        })
        obsolete_memory_id = obsolete_result.data["id"]

        # Mark the second memory as obsolete
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'mark_memory_obsolete', 'arguments': {
                'memory_id': obsolete_memory_id,
                'reason': 'Testing obsolete filtering in get_recent_memories'
            }
        })

        # Get recent memories - should exclude obsolete
        recent_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_recent_memories', 'arguments': {
                'limit': 10
            }
        })

        assert recent_result.content is not None
        import json
        memories = json.loads(recent_result.content[0].text)
        recent_ids = [m["id"] for m in memories]

        # Should include active memory
        assert active_memory_id in recent_ids
        # Should NOT include obsolete memory
        assert obsolete_memory_id not in recent_ids
