"""
E2E tests for entity MCP tools with real PostgreSQL database
"""
import pytest


@pytest.mark.asyncio
async def test_create_entity_basic_e2e(mcp_client):
    """Test creating an entity with all fields"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Acme Corporation', 'entity_type': 'Organization', 'notes':
        'A leading software company', 'tags': ['tech', 'b2b',
        'enterprise']}})
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["name"] == 'Acme Corporation'
    assert result.data["entity_type"] == 'Organization'
    assert result.data["notes"] == 'A leading software company'
    assert result.data["tags"] == ['tech', 'b2b', 'enterprise']
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.asyncio
async def test_create_entity_with_custom_type_e2e(mcp_client):
    """Test creating entity with custom type"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Temperature Sensor A1', 'entity_type': 'Other', 'custom_type':
        'IoT Sensor', 'notes': 'Temperature monitoring device', 'tags':
        ['hardware', 'iot']}})
    assert result.data is not None
    assert result.data["entity_type"] == 'Other'
    assert result.data["custom_type"] == 'IoT Sensor'


@pytest.mark.asyncio
async def test_get_entity_e2e(mcp_client):
    """Test creating then retrieving an entity"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Test Entity', 'entity_type': 'Individual', 'tags': ['test']}})
    entity_id = create_result.data["id"]
    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_entity', 'arguments': {'entity_id': entity_id}})
    assert get_result.data is not None
    assert get_result.data["id"] == entity_id
    assert get_result.data["name"] == 'Test Entity'


@pytest.mark.asyncio
async def test_list_entities_e2e(mcp_client):
    """Test listing entities"""
    entity_names = ['entity-list-1', 'entity-list-2', 'entity-list-3']
    for name in entity_names:
        await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity', 'arguments': {'name': name, 'entity_type':
            'Organization', 'tags': ['list-test']}})
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_entities', 'arguments': {}})
    assert list_result.data is not None
    assert 'entities' in list_result.data
    assert 'total_count' in list_result.data
    entities = list_result.data['entities']
    assert len(entities) >= 3
    entity_names_in_result = [e['name'] for e in entities]
    for name in entity_names:
        assert name in entity_names_in_result


@pytest.mark.asyncio
async def test_list_entities_filter_by_type_e2e(mcp_client
    ):
    """Test filtering entities by type"""
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity', 'arguments': {'name': 'Test Company',
        'entity_type': 'Organization', 'tags': ['filter-test']}})
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity', 'arguments': {'name': 'Test Person',
        'entity_type': 'Individual', 'tags': ['filter-test']}})
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_entities', 'arguments': {'entity_type':
        'Organization'}})
    entities = list_result.data['entities']
    org_entities = [e for e in entities if 'filter-test' in e['tags']]
    assert len(org_entities) >= 1
    assert all(e['entity_type'] == 'Organization' for e in org_entities)


@pytest.mark.asyncio
async def test_list_entities_filter_by_tags_e2e(mcp_client
    ):
    """Test filtering entities by tags"""
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity', 'arguments': {'name': 'Engineering Team',
        'entity_type': 'Team', 'tags': ['engineering', 'tag-filter-test']}}
        )
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity', 'arguments': {'name': 'Sales Team',
        'entity_type': 'Team', 'tags': ['sales', 'tag-filter-test']}})
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_entities', 'arguments': {'tags': [
        'engineering']}})
    entities = list_result.data['entities']
    eng_entities = [e for e in entities if 'tag-filter-test' in e['tags']]
    assert len(eng_entities) >= 1
    assert all('engineering' in e['tags'] for e in eng_entities)


@pytest.mark.asyncio
async def test_update_entity_e2e(mcp_client):
    """Test updating an entity (PATCH semantics)"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Original Name', 'entity_type': 'Organization', 'notes':
        'Original notes', 'tags': ['original']}})
    entity_id = create_result.data["id"]
    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_entity', 'arguments': {'entity_id':
        entity_id, 'name': 'Updated Name', 'notes': 'Updated notes'}})
    assert update_result.data["name"] == 'Updated Name'
    assert update_result.data["notes"] == 'Updated notes'
    assert update_result.data["tags"] == ['original']


@pytest.mark.asyncio
async def test_delete_entity_e2e(mcp_client):
    """Test deleting an entity"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'To Delete',
        'entity_type': 'Organization', 'tags': []}})
    entity_id = create_result.data["id"]
    delete_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'delete_entity', 'arguments': {'entity_id':
        entity_id}})
    assert delete_result.data is not None
    assert delete_result.data['deleted_id'] == entity_id
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
            'get_entity', 'arguments': {'entity_id': entity_id}})
        assert False, 'Expected error for deleted entity'
    except Exception as e:
        assert 'not found' in str(e).lower()


@pytest.mark.asyncio
async def test_link_entity_to_memory_e2e(mcp_client):
    """Test linking entity to memory"""
    entity_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Test Entity', 'entity_type': 'Organization', 'tags': []}})
    entity_id = entity_result.data["id"]
    memory_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Test Memory', 'content': 'Memory for linking test', 'context':
        'Testing entity-memory linking', 'keywords': ['test'], 'tags':
        [], 'importance': 7}})
    memory_id = memory_result.data["id"]
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_entity_to_memory', 'arguments': {'entity_id':
        entity_id, 'memory_id': memory_id}})
    assert link_result.data is not None
    assert link_result.data['success'] is True


@pytest.mark.asyncio
async def test_unlink_entity_from_memory_e2e(mcp_client):
    """Test unlinking entity from memory"""
    entity_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name':
        'Test Entity', 'entity_type': 'Organization', 'tags': []}})
    entity_id = entity_result.data["id"]
    memory_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory', 'arguments': {'title':
        'Test Memory', 'content': 'Memory for unlink test', 'context':
        'Testing entity-memory unlinking', 'keywords': ['test'], 'tags':
        [], 'importance': 7}})
    memory_id = memory_result.data["id"]
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'link_entity_to_memory', 'arguments': {'entity_id': entity_id,
        'memory_id': memory_id}})
    unlink_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'unlink_entity_from_memory', 'arguments': {
        'entity_id': entity_id, 'memory_id': memory_id}})
    assert unlink_result.data is not None
    assert unlink_result.data['success'] is True


@pytest.mark.asyncio
async def test_create_entity_relationship_e2e(mcp_client):
    """Test creating relationship between entities"""
    entity1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Company A',
        'entity_type': 'Organization', 'tags': []}})
    entity1_id = entity1_result.data["id"]
    entity2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Person B',
        'entity_type': 'Individual', 'tags': []}})
    entity2_id = entity2_result.data["id"]
    rel_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity_relationship', 'arguments': {
        'source_entity_id': entity1_id, 'target_entity_id': entity2_id,
        'relationship_type': 'employs', 'strength': 0.9, 'confidence': 
        0.85, 'metadata': {'role': 'engineer', 'department': 'R&D'}}})
    assert rel_result.data is not None
    assert rel_result.data["id"] is not None
    assert rel_result.data["source_entity_id"] == entity1_id
    assert rel_result.data["target_entity_id"] == entity2_id
    assert rel_result.data["relationship_type"] == 'employs'
    assert rel_result.data["strength"] == 0.9
    assert rel_result.data["confidence"] == 0.85
    assert rel_result.data["metadata"] == {'role': 'engineer',
        'department': 'R&D'}


@pytest.mark.asyncio
async def test_get_entity_relationships_e2e(mcp_client):
    """Test retrieving entity relationships"""
    entity1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Org X',
        'entity_type': 'Organization', 'tags': []}})
    entity1_id = entity1_result.data["id"]
    entity2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Person Y',
        'entity_type': 'Individual', 'tags': []}})
    entity2_id = entity2_result.data["id"]
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity_relationship', 'arguments': {'source_entity_id':
        entity1_id, 'target_entity_id': entity2_id, 'relationship_type':
        'collaborates_with'}})
    rel_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_entity_relationships', 'arguments': {
        'entity_id': entity1_id}})
    assert rel_result.data is not None
    assert 'relationships' in rel_result.data
    relationships = rel_result.data['relationships']
    assert len(relationships) >= 1
    assert any(r['source_entity_id'] == entity1_id for r in relationships)


@pytest.mark.asyncio
async def test_get_entity_relationships_filter_direction_e2e(mcp_client):
    """Test filtering relationships by direction"""
    entity1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity 1',
        'entity_type': 'Organization', 'tags': []}})
    entity1_id = entity1_result.data["id"]
    entity2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity 2',
        'entity_type': 'Individual', 'tags': []}})
    entity2_id = entity2_result.data["id"]
    await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
        'create_entity_relationship', 'arguments': {'source_entity_id':
        entity1_id, 'target_entity_id': entity2_id, 'relationship_type':
        'manages'}})
    outgoing_result = await mcp_client.call_tool('execute_forgetful_tool',
        {'tool_name': 'get_entity_relationships', 'arguments': {
        'entity_id': entity1_id, 'direction': 'outgoing'}})
    relationships = outgoing_result.data['relationships']
    assert len(relationships) >= 1
    assert all(r['source_entity_id'] == entity1_id for r in relationships)
    incoming_result = await mcp_client.call_tool('execute_forgetful_tool',
        {'tool_name': 'get_entity_relationships', 'arguments': {
        'entity_id': entity1_id, 'direction': 'incoming'}})
    incoming_rels = incoming_result.data['relationships']
    incoming_test_rels = [r for r in incoming_rels if r[
        'target_entity_id'] == entity1_id and r['source_entity_id'] ==
        entity2_id]
    assert len(incoming_test_rels) == 0


@pytest.mark.asyncio
async def test_update_entity_relationship_e2e(mcp_client):
    """Test updating entity relationship"""
    entity1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity A',
        'entity_type': 'Organization', 'tags': []}})
    entity1_id = entity1_result.data["id"]
    entity2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity B',
        'entity_type': 'Individual', 'tags': []}})
    entity2_id = entity2_result.data["id"]
    rel_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity_relationship', 'arguments': {
        'source_entity_id': entity1_id, 'target_entity_id': entity2_id,
        'relationship_type': 'partners_with', 'strength': 0.5}})
    rel_id = rel_result.data["id"]
    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_entity_relationship', 'arguments': {
        'relationship_id': rel_id, 'strength': 0.95, 'confidence': 0.9,
        'metadata': {'updated': True}}})
    assert update_result.data["strength"] == 0.95
    assert update_result.data["confidence"] == 0.9
    assert update_result.data["metadata"] == {'updated': True}
    assert update_result.data["relationship_type"] == 'partners_with'


@pytest.mark.asyncio
async def test_delete_entity_relationship_e2e(mcp_client):
    """Test deleting entity relationship"""
    entity1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity X',
        'entity_type': 'Organization', 'tags': []}})
    entity1_id = entity1_result.data["id"]
    entity2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {'name': 'Entity Y',
        'entity_type': 'Individual', 'tags': []}})
    entity2_id = entity2_result.data["id"]
    rel_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity_relationship', 'arguments': {
        'source_entity_id': entity1_id, 'target_entity_id': entity2_id,
        'relationship_type': 'works_with'}})
    rel_id = rel_result.data["id"]
    delete_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'delete_entity_relationship', 'arguments': {
        'relationship_id': rel_id}})
    assert delete_result.data is not None
    assert delete_result.data['deleted_id'] == rel_id
    rel_list = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_entity_relationships', 'arguments': {
        'entity_id': entity1_id}})
    relationships = rel_list.data['relationships']
    assert not any(r['id'] == rel_id for r in relationships)


@pytest.mark.asyncio
async def test_get_entity_not_found_e2e(mcp_client):
    """Test error handling for non-existent entity"""
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {'tool_name':
            'get_entity', 'arguments': {'entity_id': 999999}})
        assert False, 'Expected error for non-existent entity'
    except Exception as e:
        assert 'not found' in str(e).lower()
