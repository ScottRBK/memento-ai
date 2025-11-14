"""
E2E tests for link_memories tool with auto-linking disabled.

These tests verify manual linking functionality in isolation by disabling
the auto-linking feature (MEMORY_NUM_AUTO_LINK=0) to ensure we're testing
manual linking, not auto-linking side effects.
"""
import pytest
from fastmcp.client import Client
DOCKER_ENV_OVERRIDE = {'MEMORY_NUM_AUTO_LINK': '0'}


@pytest.fixture(autouse=True)
def disable_auto_linking():
    """Disable auto-linking for these tests"""
    from app.config.settings import settings
    original_value = settings.MEMORY_NUM_AUTO_LINK
    settings.MEMORY_NUM_AUTO_LINK = 0
    yield
    settings.MEMORY_NUM_AUTO_LINK = original_value


@pytest.mark.asyncio
async def test_link_memories_basic_e2e(mcp_client):
    """Test basic manual linking between two dissimilar memories"""
    result1 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Machine Learning Basics', 'content':
        'Machine learning is a subset of AI focused on pattern recognition'
        , 'context':
        'Testing manual linking between dissimilar memories',
        'keywords': ['machine-learning', 'ai', 'patterns'], 'tags': [
        'ml', 'basics'], 'importance': 7}})
    assert result1.data is not None
    memory1_id = result1.data["id"]
    result2 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'CSS Grid Layout', 'content':
        'CSS Grid provides a two-dimensional layout system for web design',
        'context': 'Testing manual linking - dissimilar to ML memory',
        'keywords': ['css', 'web', 'layout'], 'tags': ['frontend',
        'css'], 'importance': 7}})
    assert result2.data is not None
    memory2_id = result2.data["id"]
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_memories', 'arguments': {'memory_id':
        memory1_id, 'related_ids': [memory2_id]}})
    assert link_result.data is not None
    assert isinstance(link_result.data["linked_memory_ids"], list)
    assert memory2_id in link_result.data["linked_memory_ids"], f'Expected [{memory2_id}] but got {link_result.data["linked_memory_ids"]}'
    query_result1 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'Machine Learning Basics', 'query_context':
        'verifying bidirectional link from memory1', 'k': 10,
        'include_links': False}})
    found_memory1 = None
    for memory in query_result1.data["primary_memories"]:
        if memory["id"] == memory1_id:
            found_memory1 = memory
            break
    assert found_memory1 is not None
    assert memory2_id in found_memory1["linked_memory_ids"]
    query_result2 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'CSS Grid Layout', 'query_context':
        'verifying bidirectional link from memory2', 'k': 10,
        'include_links': False}})
    found_memory2 = None
    for memory in query_result2.data["primary_memories"]:
        if memory["id"] == memory2_id:
            found_memory2 = memory
            break
    assert found_memory2 is not None
    assert memory1_id in found_memory2["linked_memory_ids"]


@pytest.mark.asyncio
async def test_link_memories_batch_e2e(mcp_client):
    """Test linking one memory to multiple targets in single call"""
    source_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Database Indexing Strategies', 'content':
        'Indexes improve query performance but add write overhead',
        'context': 'Testing batch linking - source memory', 'keywords':
        ['database', 'indexing', 'performance'], 'tags': ['database',
        'optimization'], 'importance': 8}})
    assert source_result.data is not None
    source_id = source_result.data["id"]
    target1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Observer Pattern', 'content':
        'Observer pattern defines one-to-many dependency between objects',
        'context': 'Testing batch linking - target 1', 'keywords': [
        'design-patterns', 'observer', 'behavioral'], 'tags': [
        'patterns', 'oop'], 'importance': 7}})
    assert target1_result.data is not None
    target1_id = target1_result.data["id"]
    target2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'CI/CD Pipeline Best Practices', 'content':
        'Continuous integration and deployment automate software delivery',
        'context': 'Testing batch linking - target 2', 'keywords': [
        'cicd', 'devops', 'automation'], 'tags': ['devops',
        'deployment'], 'importance': 7}})
    assert target2_result.data is not None
    target2_id = target2_result.data["id"]
    target3_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'OAuth 2.0 Flow', 'content':
        'OAuth 2.0 provides delegated authorization framework',
        'context': 'Testing batch linking - target 3', 'keywords': [
        'oauth', 'security', 'authentication'], 'tags': ['security',
        'auth'], 'importance': 8}})
    assert target3_result.data is not None
    target3_id = target3_result.data["id"]
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_memories', 'arguments': {'memory_id':
        source_id, 'related_ids': [target1_id, target2_id, target3_id]}})
    assert link_result.data is not None
    assert isinstance(link_result.data["linked_memory_ids"], list)
    assert set(link_result.data["linked_memory_ids"]) == {target1_id, target2_id, target3_id
        }, f'Expected all 3 IDs, got {link_result.data["linked_memory_ids"]}'
    query_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'Database Indexing Strategies', 'query_context':
        'verifying batch links from source', 'k': 10, 'include_links': 
        False}})
    found_source = None
    for memory in query_result.data["primary_memories"]:
        if memory["id"] == source_id:
            found_source = memory
            break
    assert found_source is not None
    assert target1_id in found_source["linked_memory_ids"]
    assert target2_id in found_source["linked_memory_ids"]
    assert target3_id in found_source["linked_memory_ids"]


@pytest.mark.asyncio
async def test_link_memories_persistence_e2e(mcp_client):
    """Test that manual links persist to database across operations"""
    memory1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Graph Algorithms', 'content':
        "Dijkstra's algorithm finds shortest paths in weighted graphs",
        'context': 'Testing link persistence - memory 1', 'keywords': [
        'algorithms', 'graphs', 'dijkstra'], 'tags': ['algorithms',
        'graphs'], 'importance': 8}})
    assert memory1_result.data is not None
    memory1_id = memory1_result.data["id"]
    memory2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Microservices Architecture', 'content':
        'Microservices decompose applications into loosely coupled services'
        , 'context': 'Testing link persistence - memory 2', 'keywords':
        ['microservices', 'architecture', 'distributed'], 'tags': [
        'architecture', 'services'], 'importance': 8}})
    assert memory2_result.data is not None
    memory2_id = memory2_result.data["id"]
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_memories', 'arguments': {'memory_id':
        memory1_id, 'related_ids': [memory2_id]}})
    assert link_result.data is not None
    assert memory2_id in link_result.data["linked_memory_ids"], f'Expected [{memory2_id}] but got {link_result.data["linked_memory_ids"]}'
    query1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'Graph Algorithms', 'query_context':
        'verifying persistence of links', 'k': 10, 'include_links': False}}
        )
    found_memory1 = None
    for memory in query1_result.data["primary_memories"]:
        if memory["id"] == memory1_id:
            found_memory1 = memory
            break
    assert found_memory1 is not None
    assert memory2_id in found_memory1["linked_memory_ids"], 'Link should persist in memory1'
    query2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'Microservices Architecture', 'query_context':
        'verifying bidirectional persistence', 'k': 10, 'include_links':
        False}})
    found_memory2 = None
    for memory in query2_result.data["primary_memories"]:
        if memory["id"] == memory2_id:
            found_memory2 = memory
            break
    assert found_memory2 is not None
    assert memory1_id in found_memory2["linked_memory_ids"], 'Bidirectional link should persist in memory2'


@pytest.mark.asyncio
async def test_link_memories_partial_failure_e2e(mcp_client):
    """Test partial success when some target IDs are invalid"""
    source_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'REST API Design', 'content':
        'RESTful APIs use HTTP methods for CRUD operations', 'context':
        'Testing partial failure handling - source', 'keywords': [
        'rest', 'api', 'http'], 'tags': ['api', 'rest'], 'importance': 7}})
    assert source_result.data is not None
    source_id = source_result.data["id"]
    target_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'GraphQL Query Language', 'content':
        'GraphQL provides a flexible query language for APIs',
        'context': 'Testing partial failure handling - valid target',
        'keywords': ['graphql', 'api', 'queries'], 'tags': ['api',
        'graphql'], 'importance': 7}})
    assert target_result.data is not None
    valid_target_id = target_result.data["id"]
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_memories', 'arguments': {'memory_id':
        source_id, 'related_ids': [valid_target_id, 999999]}})
    assert link_result.data is not None
    assert isinstance(link_result.data["linked_memory_ids"], list)
    assert valid_target_id in link_result.data["linked_memory_ids"], f'Expected valid ID {valid_target_id} in result'
    assert 999999 not in link_result.data["linked_memory_ids"], 'Invalid ID should be skipped'
    query_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'REST API Design', 'query_context': 'verifying partial success',
        'k': 10, 'include_links': False}})
    found_source = None
    for memory in query_result.data["primary_memories"]:
        if memory["id"] == source_id:
            found_source = memory
            break
    assert found_source is not None
    assert valid_target_id in found_source["linked_memory_ids"]
    assert 999999 not in found_source["linked_memory_ids"]


@pytest.mark.asyncio
async def test_link_memories_duplicate_prevention_e2e(mcp_client):
    """Test that duplicate link attempts are handled gracefully"""
    memory1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Binary Search Trees', 'content':
        'BST is a data structure with ordered node arrangement',
        'context': 'Testing duplicate prevention - memory 1',
        'keywords': ['bst', 'trees', 'data-structures'], 'tags': [
        'data-structures', 'trees'], 'importance': 7}})
    assert memory1_result.data is not None
    memory1_id = memory1_result.data["id"]
    memory2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Kubernetes Deployments', 'content':
        'Kubernetes manages containerized application deployments',
        'context': 'Testing duplicate prevention - memory 2',
        'keywords': ['kubernetes', 'containers', 'orchestration'],
        'tags': ['k8s', 'devops'], 'importance': 8}})
    assert memory2_result.data is not None
    memory2_id = memory2_result.data["id"]
    first_link_result = await mcp_client.call_tool('execute_forgetful_tool',
        {'tool_name': 'link_memories', 'arguments': {'memory_id':
        memory1_id, 'related_ids': [memory2_id]}})
    assert first_link_result.data is not None
    assert memory2_id in first_link_result.data["linked_memory_ids"], f'Expected [{memory2_id}] but got {first_link_result.data["linked_memory_ids"]}'
    second_link_result = await mcp_client.call_tool('execute_forgetful_tool',
        {'tool_name': 'link_memories', 'arguments': {'memory_id':
        memory1_id, 'related_ids': [memory2_id]}})
    assert second_link_result.data is not None
    assert isinstance(second_link_result.data["linked_memory_ids"], list)
    assert len(second_link_result.data["linked_memory_ids"]
        ) == 0, f'Expected empty list for duplicate, got {second_link_result.data["linked_memory_ids"]}'
    query_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'query_memory', 'arguments': {'query':
        'Binary Search Trees', 'query_context':
        'verifying no duplicate links', 'k': 10, 'include_links': False}})
    found_memory = None
    for memory in query_result.data["primary_memories"]:
        if memory["id"] == memory1_id:
            found_memory = memory
            break
    assert found_memory is not None
    link_count = found_memory["linked_memory_ids"].count(memory2_id)
    assert link_count == 1, 'Should have exactly one link, no duplicates'


@pytest.mark.asyncio
async def test_link_memories_invalid_source_id_e2e(mcp_client):
    """Test error handling when source memory doesn't exist"""
    target_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Test Target Memory', 'content':
        'This is a valid target memory for error testing', 'context':
        'Testing error handling with invalid source', 'keywords': [
        'test', 'error', 'handling'], 'tags': ['test'], 'importance': 7}})
    assert target_result.data is not None
    target_id = target_result.data["id"]
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
            'link_memories', 'arguments': {'memory_id': 999999,
            'related_ids': [target_id]}})
        assert False, 'Expected ToolError for invalid source memory_id'
    except Exception as e:
        error_message = str(e)
        assert 'not found' in error_message.lower(
            ) or 'validation_error' in error_message.lower()
