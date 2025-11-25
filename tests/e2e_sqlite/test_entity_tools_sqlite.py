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
async def test_create_entity_case_insensitive_type_e2e(mcp_client):
    """Test entity_type is case-insensitive"""
    # lowercase
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Test Lowercase', 'entity_type': 'individual', 'tags': []
        }
    })
    assert result.data["entity_type"] == 'Individual'

    # UPPERCASE
    result2 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Test Uppercase', 'entity_type': 'ORGANIZATION', 'tags': []
        }
    })
    assert result2.data["entity_type"] == 'Organization'


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


@pytest.mark.asyncio
async def test_search_entities_basic_e2e(mcp_client):
    """Test basic entity search by name"""
    # Create entities with different names
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'TechCorp Solutions SQLite',
            'entity_type': 'Organization',
            'tags': ['search-test-sqlite']
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'TechFlow Systems SQLite',
            'entity_type': 'Organization',
            'tags': ['search-test-sqlite']
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Sarah Chen SQLite',
            'entity_type': 'Individual',
            'tags': ['search-test-sqlite']
        }
    })

    # Search for "tech"
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'tech'
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    assert 'entities' in result_data
    assert 'total_count' in result_data
    entities = result_data['entities']

    # Filter to our test entities
    test_entities = [e for e in entities if 'search-test-sqlite' in e['tags']]
    assert len(test_entities) >= 2
    assert all('tech' in e['name'].lower() for e in test_entities)


@pytest.mark.asyncio
async def test_search_entities_case_insensitive_e2e(mcp_client):
    """Test that entity search is case-insensitive"""
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'UPPERCASE ORGANIZATION SQLITE',
            'entity_type': 'Organization',
            'tags': ['case-test-sqlite']
        }
    })

    # Search with lowercase should find it
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'uppercase',
            'tags': ['case-test-sqlite']
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    entities = result_data['entities']
    assert len(entities) >= 1
    assert any(e['name'] == 'UPPERCASE ORGANIZATION SQLITE' for e in entities)


@pytest.mark.asyncio
async def test_search_entities_with_type_filter_e2e(mcp_client):
    """Test searching entities filtered by entity type"""
    # Create different types
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Server Alpha SQLite',
            'entity_type': 'Device',
            'tags': ['type-filter-test-sqlite']
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Server Beta SQLite',
            'entity_type': 'Device',
            'tags': ['type-filter-test-sqlite']
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Server Team SQLite',
            'entity_type': 'Team',
            'tags': ['type-filter-test-sqlite']
        }
    })

    # Search for "server" but only devices
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'server',
            'entity_type': 'Device',
            'tags': ['type-filter-test-sqlite']
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    entities = result_data['entities']
    assert len(entities) >= 2
    assert all(e['entity_type'] == 'Device' for e in entities)


@pytest.mark.asyncio
async def test_search_entities_with_tags_filter_e2e(mcp_client):
    """Test searching entities filtered by tags"""
    # Create entities with different tags
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Production Server SQLite',
            'entity_type': 'Device',
            'tags': ['production', 'tag-search-test-sqlite']
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Staging Server SQLite',
            'entity_type': 'Device',
            'tags': ['staging', 'tag-search-test-sqlite']
        }
    })

    # Search for "server" with production tag
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'server',
            'tags': ['production']
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    entities = result_data['entities']
    prod_entities = [e for e in entities if 'tag-search-test-sqlite' in e['tags']]
    assert len(prod_entities) >= 1
    assert all('production' in e['tags'] for e in prod_entities)


@pytest.mark.asyncio
async def test_search_entities_limit_e2e(mcp_client):
    """Test that search respects limit parameter"""
    # Create many entities
    for i in range(10):
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': f'Limit Test Entity SQLite {i}',
                'entity_type': 'Organization',
                'tags': ['limit-test-sqlite']
            }
        })

    # Search with limit
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'limit test',
            'limit': 3
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    entities = result_data['entities']
    limit_test_entities = [e for e in entities if 'limit-test-sqlite' in e['tags']]
    assert len(limit_test_entities) <= 3


@pytest.mark.asyncio
async def test_search_entities_no_results_e2e(mcp_client):
    """Test search returns empty when no matches found"""
    # Search for something that definitely doesn't exist
    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_entities', 'arguments': {
            'query': 'xyznonexistententitysqlite12345'
        }
    })

    assert search_result.content is not None
    import json
    result_data = json.loads(search_result.content[0].text)
    assert 'entities' in result_data
    assert 'total_count' in result_data
    # May have results from other tests, but none should match our query
    entities = result_data['entities']
    assert all('xyznonexistententitysqlite12345' not in e['name'].lower() for e in entities)


# Entity-Project Many-to-Many Relationship E2E Tests


@pytest.mark.asyncio
async def test_create_entity_with_multiple_projects_e2e(mcp_client):
    """Test creating entity with multiple project associations"""
    # Create test projects first
    project1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Test Project 1 for Entity',
            'description': 'First test project',
            'project_type': 'development'
        }
    })
    project1_id = project1_result.data["id"]

    project2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Test Project 2 for Entity',
            'description': 'Second test project',
            'project_type': 'development'
        }
    })
    project2_id = project2_result.data["id"]

    # Create entity with multiple projects
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Multi-Project Entity E2E',
            'entity_type': 'Organization',
            'notes': 'Associated with multiple projects',
            'tags': ['multi-project-e2e'],
            'project_ids': [project1_id, project2_id]
        }
    })

    assert result.data is not None
    assert result.data["id"] is not None
    assert len(result.data["project_ids"]) == 2
    assert project1_id in result.data["project_ids"]
    assert project2_id in result.data["project_ids"]


@pytest.mark.asyncio
async def test_create_entity_with_no_projects_e2e(mcp_client):
    """Test creating entity with no project associations"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'No Project Entity E2E',
            'entity_type': 'Individual',
            'notes': 'No project associations',
            'tags': ['unassociated-e2e']
        }
    })

    assert result.data is not None
    assert result.data["id"] is not None
    assert len(result.data["project_ids"]) == 0


@pytest.mark.asyncio
async def test_get_entity_with_project_ids_e2e(mcp_client):
    """Test retrieving entity and verifying project_ids are loaded"""
    # Create project
    project_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Get Entity Test Project',
            'description': 'Project for get entity test',
            'project_type': 'development'
        }
    })
    project_id = project_result.data["id"]

    # Create entity with project
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Get Test Entity E2E',
            'entity_type': 'Organization',
            'tags': ['get-test-e2e'],
            'project_ids': [project_id]
        }
    })
    entity_id = create_result.data["id"]

    # Get entity and verify project_ids
    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_entity', 'arguments': {'entity_id': entity_id}
    })

    assert get_result.data is not None
    assert get_result.data["id"] == entity_id
    assert len(get_result.data["project_ids"]) == 1
    assert project_id in get_result.data["project_ids"]


@pytest.mark.asyncio
async def test_list_entities_filter_by_project_ids_e2e(mcp_client):
    """Test filtering entities by project_ids"""
    # Create test projects
    project1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Filter Test Project 1',
            'description': 'First filter test project',
            'project_type': 'development'
        }
    })
    project1_id = project1_result.data["id"]

    project2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Filter Test Project 2',
            'description': 'Second filter test project',
            'project_type': 'development'
        }
    })
    project2_id = project2_result.data["id"]

    # Create entities with different project associations
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Project 1 Only Entity E2E',
            'entity_type': 'Organization',
            'tags': ['proj-filter-e2e'],
            'project_ids': [project1_id]
        }
    })

    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Project 2 Only Entity E2E',
            'entity_type': 'Organization',
            'tags': ['proj-filter-e2e'],
            'project_ids': [project2_id]
        }
    })

    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Both Projects Entity E2E',
            'entity_type': 'Organization',
            'tags': ['proj-filter-e2e'],
            'project_ids': [project1_id, project2_id]
        }
    })

    # Filter by project 1
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_entities', 'arguments': {
            'project_ids': [project1_id]
        }
    })

    entities = list_result.data['entities']
    proj_filter_entities = [e for e in entities if 'proj-filter-e2e' in e['tags']]

    # Should find 2 entities (one with project 1 only, one with both)
    assert len(proj_filter_entities) == 2

    # Filter by project 2
    list_result2 = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_entities', 'arguments': {
            'project_ids': [project2_id]
        }
    })

    entities2 = list_result2.data['entities']
    proj_filter_entities2 = [e for e in entities2 if 'proj-filter-e2e' in e['tags']]

    # Should find 2 entities (one with project 2 only, one with both)
    assert len(proj_filter_entities2) == 2


@pytest.mark.asyncio
async def test_update_entity_change_projects_e2e(mcp_client):
    """Test updating entity to change project associations"""
    # Create test projects
    project1_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Update Test Project 1',
            'description': 'First update test project',
            'project_type': 'development'
        }
    })
    project1_id = project1_result.data["id"]

    project2_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Update Test Project 2',
            'description': 'Second update test project',
            'project_type': 'development'
        }
    })
    project2_id = project2_result.data["id"]

    project3_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Update Test Project 3',
            'description': 'Third update test project',
            'project_type': 'development'
        }
    })
    project3_id = project3_result.data["id"]

    # Create entity with initial projects
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Project Update Entity E2E',
            'entity_type': 'Organization',
            'notes': 'Testing project updates',
            'tags': ['update-test-e2e'],
            'project_ids': [project1_id, project2_id]
        }
    })
    entity_id = create_result.data["id"]

    assert len(create_result.data["project_ids"]) == 2

    # Update to change projects (remove project1, keep project2, add project3)
    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_entity', 'arguments': {
            'entity_id': entity_id,
            'project_ids': [project2_id, project3_id]
        }
    })

    assert len(update_result.data["project_ids"]) == 2
    assert project2_id in update_result.data["project_ids"]
    assert project3_id in update_result.data["project_ids"]
    assert project1_id not in update_result.data["project_ids"]


@pytest.mark.asyncio
async def test_update_entity_clear_all_projects_e2e(mcp_client):
    """Test updating entity to clear all project associations"""
    # Create test project
    project_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project', 'arguments': {
            'name': 'Clear Test Project',
            'description': 'Project for clear test',
            'project_type': 'development'
        }
    })
    project_id = project_result.data["id"]

    # Create entity with project
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_entity', 'arguments': {
            'name': 'Clear Projects Entity E2E',
            'entity_type': 'Organization',
            'tags': ['clear-test-e2e'],
            'project_ids': [project_id]
        }
    })
    entity_id = create_result.data["id"]

    assert len(create_result.data["project_ids"]) == 1

    # Update to clear all projects
    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_entity', 'arguments': {
            'entity_id': entity_id,
            'project_ids': []
        }
    })

    assert len(update_result.data["project_ids"]) == 0
