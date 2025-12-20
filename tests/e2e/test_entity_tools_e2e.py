"""
E2E tests for entity MCP tools with real PostgreSQL database
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_basic_e2e(docker_services, mcp_server_url):
    """Test creating an entity with all fields"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool('execute_forgetful_tool', {
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_with_custom_type_e2e(docker_services,
    mcp_server_url):
    """Test creating entity with custom type"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name':
            'Temperature Sensor A1', 'entity_type': 'Other', 'custom_type':
            'IoT Sensor', 'notes': 'Temperature monitoring device', 'tags':
            ['hardware', 'iot']}})
        assert result.data is not None
        assert result.data["entity_type"] == 'Other'
        assert result.data["custom_type"] == 'IoT Sensor'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_e2e(docker_services, mcp_server_url):
    """Test creating then retrieving an entity"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name':
            'Test Entity', 'entity_type': 'Individual', 'tags': ['test']}})
        entity_id = create_result.data["id"]
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity', 'arguments': {'entity_id': entity_id}})
        assert get_result.data is not None
        assert get_result.data["id"] == entity_id
        assert get_result.data["name"] == 'Test Entity'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_e2e(docker_services, mcp_server_url):
    """Test listing entities"""
    async with Client(mcp_server_url) as client:
        entity_names = ['entity-list-1', 'entity-list-2', 'entity-list-3']
        for name in entity_names:
            await client.call_tool('execute_forgetful_tool', {'tool_name':
                'create_entity', 'arguments': {'name': name, 'entity_type':
                'Organization', 'tags': ['list-test']}})
        list_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'list_entities', 'arguments': {}})
        assert list_result.data is not None
        assert 'entities' in list_result.data
        assert 'total_count' in list_result.data
        entities = list_result.data['entities']
        assert len(entities) >= 3
        entity_names_in_result = [e['name'] for e in entities]
        for name in entity_names:
            assert name in entity_names_in_result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_filter_by_type_e2e(docker_services, mcp_server_url
    ):
    """Test filtering entities by type"""
    async with Client(mcp_server_url) as client:
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity', 'arguments': {'name': 'Test Company',
            'entity_type': 'Organization', 'tags': ['filter-test']}})
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity', 'arguments': {'name': 'Test Person',
            'entity_type': 'Individual', 'tags': ['filter-test']}})
        list_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'list_entities', 'arguments': {'entity_type':
            'Organization'}})
        entities = list_result.data['entities']
        org_entities = [e for e in entities if 'filter-test' in e['tags']]
        assert len(org_entities) >= 1
        assert all(e['entity_type'] == 'Organization' for e in org_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_filter_by_tags_e2e(docker_services, mcp_server_url
    ):
    """Test filtering entities by tags"""
    async with Client(mcp_server_url) as client:
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity', 'arguments': {'name': 'Engineering Team',
            'entity_type': 'Team', 'tags': ['engineering', 'tag-filter-test']}}
            )
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity', 'arguments': {'name': 'Sales Team',
            'entity_type': 'Team', 'tags': ['sales', 'tag-filter-test']}})
        list_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'list_entities', 'arguments': {'tags': [
            'engineering']}})
        entities = list_result.data['entities']
        eng_entities = [e for e in entities if 'tag-filter-test' in e['tags']]
        assert len(eng_entities) >= 1
        assert all('engineering' in e['tags'] for e in eng_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_e2e(docker_services, mcp_server_url):
    """Test updating an entity (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name':
            'Original Name', 'entity_type': 'Organization', 'notes':
            'Original notes', 'tags': ['original']}})
        entity_id = create_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_entity', 'arguments': {'entity_id':
            entity_id, 'name': 'Updated Name', 'notes': 'Updated notes'}})
        assert update_result.data["name"] == 'Updated Name'
        assert update_result.data["notes"] == 'Updated notes'
        assert update_result.data["tags"] == ['original']


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_entity_e2e(docker_services, mcp_server_url):
    """Test deleting an entity"""
    async with Client(mcp_server_url) as client:
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'To Delete',
            'entity_type': 'Organization', 'tags': []}})
        entity_id = create_result.data["id"]
        delete_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'delete_entity', 'arguments': {'entity_id':
            entity_id}})
        assert delete_result.data is not None
        assert delete_result.data['deleted_id'] == entity_id
        try:
            await client.call_tool('execute_forgetful_tool', {'tool_name':
                'get_entity', 'arguments': {'entity_id': entity_id}})
            assert False, 'Expected error for deleted entity'
        except Exception as e:
            assert 'not found' in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_link_entity_to_memory_e2e(docker_services, mcp_server_url):
    """Test linking entity to memory"""
    async with Client(mcp_server_url) as client:
        entity_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name':
            'Test Entity', 'entity_type': 'Organization', 'tags': []}})
        entity_id = entity_result.data["id"]
        memory_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Test Memory', 'content': 'Memory for linking test', 'context':
            'Testing entity-memory linking', 'keywords': ['test'], 'tags':
            [], 'importance': 7}})
        memory_id = memory_result.data["id"]
        link_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'link_entity_to_memory', 'arguments': {'entity_id':
            entity_id, 'memory_id': memory_id}})
        assert link_result.data is not None
        assert link_result.data['success'] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_unlink_entity_from_memory_e2e(docker_services, mcp_server_url):
    """Test unlinking entity from memory"""
    async with Client(mcp_server_url) as client:
        entity_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name':
            'Test Entity', 'entity_type': 'Organization', 'tags': []}})
        entity_id = entity_result.data["id"]
        memory_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_memory', 'arguments': {'title':
            'Test Memory', 'content': 'Memory for unlink test', 'context':
            'Testing entity-memory unlinking', 'keywords': ['test'], 'tags':
            [], 'importance': 7}})
        memory_id = memory_result.data["id"]
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'link_entity_to_memory', 'arguments': {'entity_id': entity_id,
            'memory_id': memory_id}})
        unlink_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'unlink_entity_from_memory', 'arguments': {
            'entity_id': entity_id, 'memory_id': memory_id}})
        assert unlink_result.data is not None
        assert unlink_result.data['success'] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test creating relationship between entities"""
    async with Client(mcp_server_url) as client:
        entity1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Company A',
            'entity_type': 'Organization', 'tags': []}})
        entity1_id = entity1_result.data["id"]
        entity2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Person B',
            'entity_type': 'Individual', 'tags': []}})
        entity2_id = entity2_result.data["id"]
        rel_result = await client.call_tool('execute_forgetful_tool', {
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


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_relationships_e2e(docker_services, mcp_server_url):
    """Test retrieving entity relationships"""
    async with Client(mcp_server_url) as client:
        entity1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Org X',
            'entity_type': 'Organization', 'tags': []}})
        entity1_id = entity1_result.data["id"]
        entity2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Person Y',
            'entity_type': 'Individual', 'tags': []}})
        entity2_id = entity2_result.data["id"]
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity_relationship', 'arguments': {'source_entity_id':
            entity1_id, 'target_entity_id': entity2_id, 'relationship_type':
            'collaborates_with'}})
        rel_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_relationships', 'arguments': {
            'entity_id': entity1_id}})
        assert rel_result.data is not None
        assert 'relationships' in rel_result.data
        relationships = rel_result.data['relationships']
        assert len(relationships) >= 1
        assert any(r['source_entity_id'] == entity1_id for r in relationships)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_relationships_filter_direction_e2e(docker_services,
    mcp_server_url):
    """Test filtering relationships by direction"""
    async with Client(mcp_server_url) as client:
        entity1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity 1',
            'entity_type': 'Organization', 'tags': []}})
        entity1_id = entity1_result.data["id"]
        entity2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity 2',
            'entity_type': 'Individual', 'tags': []}})
        entity2_id = entity2_result.data["id"]
        await client.call_tool('execute_forgetful_tool', {'tool_name':
            'create_entity_relationship', 'arguments': {'source_entity_id':
            entity1_id, 'target_entity_id': entity2_id, 'relationship_type':
            'manages'}})
        outgoing_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'get_entity_relationships', 'arguments': {
            'entity_id': entity1_id, 'direction': 'outgoing'}})
        relationships = outgoing_result.data['relationships']
        assert len(relationships) >= 1
        assert all(r['source_entity_id'] == entity1_id for r in relationships)
        incoming_result = await client.call_tool('execute_forgetful_tool',
            {'tool_name': 'get_entity_relationships', 'arguments': {
            'entity_id': entity1_id, 'direction': 'incoming'}})
        incoming_rels = incoming_result.data['relationships']
        incoming_test_rels = [r for r in incoming_rels if r[
            'target_entity_id'] == entity1_id and r['source_entity_id'] ==
            entity2_id]
        assert len(incoming_test_rels) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test updating entity relationship"""
    async with Client(mcp_server_url) as client:
        entity1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity A',
            'entity_type': 'Organization', 'tags': []}})
        entity1_id = entity1_result.data["id"]
        entity2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity B',
            'entity_type': 'Individual', 'tags': []}})
        entity2_id = entity2_result.data["id"]
        rel_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity_relationship', 'arguments': {
            'source_entity_id': entity1_id, 'target_entity_id': entity2_id,
            'relationship_type': 'partners_with', 'strength': 0.5}})
        rel_id = rel_result.data["id"]
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_entity_relationship', 'arguments': {
            'relationship_id': rel_id, 'strength': 0.95, 'confidence': 0.9,
            'metadata': {'updated': True}}})
        assert update_result.data["strength"] == 0.95
        assert update_result.data["confidence"] == 0.9
        assert update_result.data["metadata"] == {'updated': True}
        assert update_result.data["relationship_type"] == 'partners_with'


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_entity_relationship_e2e(docker_services, mcp_server_url):
    """Test deleting entity relationship"""
    async with Client(mcp_server_url) as client:
        entity1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity X',
            'entity_type': 'Organization', 'tags': []}})
        entity1_id = entity1_result.data["id"]
        entity2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {'name': 'Entity Y',
            'entity_type': 'Individual', 'tags': []}})
        entity2_id = entity2_result.data["id"]
        rel_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity_relationship', 'arguments': {
            'source_entity_id': entity1_id, 'target_entity_id': entity2_id,
            'relationship_type': 'works_with'}})
        rel_id = rel_result.data["id"]
        delete_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'delete_entity_relationship', 'arguments': {
            'relationship_id': rel_id}})
        assert delete_result.data is not None
        assert delete_result.data['deleted_id'] == rel_id
        rel_list = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_relationships', 'arguments': {
            'entity_id': entity1_id}})
        relationships = rel_list.data['relationships']
        assert not any(r['id'] == rel_id for r in relationships)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_not_found_e2e(docker_services, mcp_server_url):
    """Test error handling for non-existent entity"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool('execute_forgetful_tool', {'tool_name':
                'get_entity', 'arguments': {'entity_id': 999999}})
            assert False, 'Expected error for non-existent entity'
        except Exception as e:
            assert 'not found' in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_basic_e2e(docker_services, mcp_server_url):
    """Test basic entity search by name"""
    async with Client(mcp_server_url) as client:
        # Create entities with different names
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'TechCorp Solutions',
                'entity_type': 'Organization',
                'tags': ['search-test']
            }
        })
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'TechFlow Systems',
                'entity_type': 'Organization',
                'tags': ['search-test']
            }
        })
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Sarah Chen',
                'entity_type': 'Individual',
                'tags': ['search-test']
            }
        })

        # Search for "tech"
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'tech'
            }
        })

        assert search_result.data is not None
        assert 'entities' in search_result.data
        assert 'total_count' in search_result.data
        entities = search_result.data['entities']

        # Filter to our test entities
        test_entities = [e for e in entities if 'search-test' in e['tags']]
        assert len(test_entities) >= 2
        assert all('tech' in e['name'].lower() for e in test_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_case_insensitive_e2e(docker_services, mcp_server_url):
    """Test that entity search is case-insensitive"""
    async with Client(mcp_server_url) as client:
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'UPPERCASE ORGANIZATION',
                'entity_type': 'Organization',
                'tags': ['case-test']
            }
        })

        # Search with lowercase should find it
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'uppercase',
                'tags': ['case-test']
            }
        })

        assert search_result.data is not None
        entities = search_result.data['entities']
        assert len(entities) >= 1
        assert any(e['name'] == 'UPPERCASE ORGANIZATION' for e in entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_with_type_filter_e2e(docker_services, mcp_server_url):
    """Test searching entities filtered by entity type"""
    async with Client(mcp_server_url) as client:
        # Create different types
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Server Alpha',
                'entity_type': 'Device',
                'tags': ['type-filter-test']
            }
        })
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Server Beta',
                'entity_type': 'Device',
                'tags': ['type-filter-test']
            }
        })
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Server Team',
                'entity_type': 'Team',
                'tags': ['type-filter-test']
            }
        })

        # Search for "server" but only devices
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'server',
                'entity_type': 'Device',
                'tags': ['type-filter-test']
            }
        })

        assert search_result.data is not None
        entities = search_result.data['entities']
        assert len(entities) >= 2
        assert all(e['entity_type'] == 'Device' for e in entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_with_tags_filter_e2e(docker_services, mcp_server_url):
    """Test searching entities filtered by tags"""
    async with Client(mcp_server_url) as client:
        # Create entities with different tags
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Production Server',
                'entity_type': 'Device',
                'tags': ['production', 'tag-search-test']
            }
        })
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Staging Server',
                'entity_type': 'Device',
                'tags': ['staging', 'tag-search-test']
            }
        })

        # Search for "server" with production tag
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'server',
                'tags': ['production']
            }
        })

        assert search_result.data is not None
        entities = search_result.data['entities']
        prod_entities = [e for e in entities if 'tag-search-test' in e['tags']]
        assert len(prod_entities) >= 1
        assert all('production' in e['tags'] for e in prod_entities)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_limit_e2e(docker_services, mcp_server_url):
    """Test that search respects limit parameter"""
    async with Client(mcp_server_url) as client:
        # Create many entities
        for i in range(10):
            await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'create_entity', 'arguments': {
                    'name': f'Limit Test Entity {i}',
                    'entity_type': 'Organization',
                    'tags': ['limit-test']
                }
            })

        # Search with limit
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'limit test',
                'limit': 3
            }
        })

        assert search_result.data is not None
        entities = search_result.data['entities']
        limit_test_entities = [e for e in entities if 'limit-test' in e['tags']]
        assert len(limit_test_entities) <= 3


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_search_entities_no_results_e2e(docker_services, mcp_server_url):
    """Test search returns empty when no matches found"""
    async with Client(mcp_server_url) as client:
        # Search for something that definitely doesn't exist
        search_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'search_entities', 'arguments': {
                'query': 'xyznonexistententity12345'
            }
        })

        assert search_result.data is not None
        assert 'entities' in search_result.data
        assert 'total_count' in search_result.data
        # May have results from other tests, but none should match our query
        entities = search_result.data['entities']
        assert all('xyznonexistententity12345' not in e['name'].lower() for e in entities)


# Entity-Project Many-to-Many Relationship E2E Tests


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_with_multiple_projects_e2e(docker_services, mcp_server_url):
    """Test creating entity with multiple project associations"""
    async with Client(mcp_server_url) as client:
        # Create test projects first
        project1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Test Project 1 for Entity Postgres',
                'description': 'First test project',
                'project_type': 'development'
            }
        })
        project1_id = project1_result.data["id"]

        project2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Test Project 2 for Entity Postgres',
                'description': 'Second test project',
                'project_type': 'development'
            }
        })
        project2_id = project2_result.data["id"]

        # Create entity with multiple projects
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Multi-Project Entity E2E Postgres',
                'entity_type': 'Organization',
                'notes': 'Associated with multiple projects',
                'tags': ['multi-project-e2e-pg'],
                'project_ids': [project1_id, project2_id]
            }
        })

        assert result.data is not None
        assert result.data["id"] is not None
        assert len(result.data["project_ids"]) == 2
        assert project1_id in result.data["project_ids"]
        assert project2_id in result.data["project_ids"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_entity_with_no_projects_e2e(docker_services, mcp_server_url):
    """Test creating entity with no project associations"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'No Project Entity E2E Postgres',
                'entity_type': 'Individual',
                'notes': 'No project associations',
                'tags': ['unassociated-e2e-pg']
            }
        })

        assert result.data is not None
        assert result.data["id"] is not None
        assert len(result.data["project_ids"]) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_with_project_ids_e2e(docker_services, mcp_server_url):
    """Test retrieving entity and verifying project_ids are loaded"""
    async with Client(mcp_server_url) as client:
        # Create project
        project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Get Entity Test Project Postgres',
                'description': 'Project for get entity test',
                'project_type': 'development'
            }
        })
        project_id = project_result.data["id"]

        # Create entity with project
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Get Test Entity E2E Postgres',
                'entity_type': 'Organization',
                'tags': ['get-test-e2e-pg'],
                'project_ids': [project_id]
            }
        })
        entity_id = create_result.data["id"]

        # Get entity and verify project_ids
        get_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity', 'arguments': {'entity_id': entity_id}
        })

        assert get_result.data is not None
        assert get_result.data["id"] == entity_id
        assert len(get_result.data["project_ids"]) == 1
        assert project_id in get_result.data["project_ids"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_entities_filter_by_project_ids_e2e(docker_services, mcp_server_url):
    """Test filtering entities by project_ids"""
    async with Client(mcp_server_url) as client:
        # Create test projects
        project1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Filter Test Project 1 Postgres',
                'description': 'First filter test project',
                'project_type': 'development'
            }
        })
        project1_id = project1_result.data["id"]

        project2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Filter Test Project 2 Postgres',
                'description': 'Second filter test project',
                'project_type': 'development'
            }
        })
        project2_id = project2_result.data["id"]

        # Create entities with different project associations
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Project 1 Only Entity E2E Postgres',
                'entity_type': 'Organization',
                'tags': ['proj-filter-e2e-pg'],
                'project_ids': [project1_id]
            }
        })

        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Project 2 Only Entity E2E Postgres',
                'entity_type': 'Organization',
                'tags': ['proj-filter-e2e-pg'],
                'project_ids': [project2_id]
            }
        })

        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Both Projects Entity E2E Postgres',
                'entity_type': 'Organization',
                'tags': ['proj-filter-e2e-pg'],
                'project_ids': [project1_id, project2_id]
            }
        })

        # Filter by project 1
        list_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'list_entities', 'arguments': {
                'project_ids': [project1_id]
            }
        })

        entities = list_result.data['entities']
        proj_filter_entities = [e for e in entities if 'proj-filter-e2e-pg' in e['tags']]

        # Should find 2 entities (one with project 1 only, one with both)
        assert len(proj_filter_entities) == 2

        # Filter by project 2
        list_result2 = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'list_entities', 'arguments': {
                'project_ids': [project2_id]
            }
        })

        entities2 = list_result2.data['entities']
        proj_filter_entities2 = [e for e in entities2 if 'proj-filter-e2e-pg' in e['tags']]

        # Should find 2 entities (one with project 2 only, one with both)
        assert len(proj_filter_entities2) == 2


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_change_projects_e2e(docker_services, mcp_server_url):
    """Test updating entity to change project associations"""
    async with Client(mcp_server_url) as client:
        # Create test projects
        project1_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Update Test Project 1 Postgres',
                'description': 'First update test project',
                'project_type': 'development'
            }
        })
        project1_id = project1_result.data["id"]

        project2_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Update Test Project 2 Postgres',
                'description': 'Second update test project',
                'project_type': 'development'
            }
        })
        project2_id = project2_result.data["id"]

        project3_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Update Test Project 3 Postgres',
                'description': 'Third update test project',
                'project_type': 'development'
            }
        })
        project3_id = project3_result.data["id"]

        # Create entity with initial projects
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Project Update Entity E2E Postgres',
                'entity_type': 'Organization',
                'notes': 'Testing project updates',
                'tags': ['update-test-e2e-pg'],
                'project_ids': [project1_id, project2_id]
            }
        })
        entity_id = create_result.data["id"]

        assert len(create_result.data["project_ids"]) == 2

        # Update to change projects (remove project1, keep project2, add project3)
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_entity', 'arguments': {
                'entity_id': entity_id,
                'project_ids': [project2_id, project3_id]
            }
        })

        assert len(update_result.data["project_ids"]) == 2
        assert project2_id in update_result.data["project_ids"]
        assert project3_id in update_result.data["project_ids"]
        assert project1_id not in update_result.data["project_ids"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_entity_clear_all_projects_e2e(docker_services, mcp_server_url):
    """Test updating entity to clear all project associations"""
    async with Client(mcp_server_url) as client:
        # Create test project
        project_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_project', 'arguments': {
                'name': 'Clear Test Project Postgres',
                'description': 'Project for clear test',
                'project_type': 'development'
            }
        })
        project_id = project_result.data["id"]

        # Create entity with project
        create_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Clear Projects Entity E2E Postgres',
                'entity_type': 'Organization',
                'tags': ['clear-test-e2e-pg'],
                'project_ids': [project_id]
            }
        })
        entity_id = create_result.data["id"]

        assert len(create_result.data["project_ids"]) == 1

        # Update to clear all projects
        update_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'update_entity', 'arguments': {
                'entity_id': entity_id,
                'project_ids': []
            }
        })

        assert len(update_result.data["project_ids"]) == 0


# Entity-Memory Query E2E Tests (get_entity_memories)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_memories_basic_e2e(docker_services, mcp_server_url):
    """Test getting memories linked to an entity via MCP tool"""
    async with Client(mcp_server_url) as client:
        # Create entity
        entity_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Entity for Memory Query PG',
                'entity_type': 'Organization',
                'tags': ['memory-query-e2e-pg']
            }
        })
        entity_id = entity_result.data["id"]

        # Create some memories
        memory_ids = []
        for i in range(3):
            memory_result = await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'create_memory', 'arguments': {
                    'title': f'Memory for Entity Query Test PG {i}',
                    'content': f'Content for memory {i}',
                    'context': 'Testing get_entity_memories',
                    'keywords': ['test'],
                    'tags': ['memory-query-e2e-pg'],
                    'importance': 7
                }
            })
            memory_ids.append(memory_result.data["id"])
            # Link to entity
            await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'link_entity_to_memory', 'arguments': {
                    'entity_id': entity_id,
                    'memory_id': memory_result.data["id"]
                }
            })

        # Get entity memories
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_memories', 'arguments': {
                'entity_id': entity_id
            }
        })

        assert result.data is not None
        assert 'memory_ids' in result.data
        assert 'count' in result.data
        assert result.data['count'] == 3
        assert len(result.data['memory_ids']) == 3
        for mid in memory_ids:
            assert mid in result.data['memory_ids']


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_memories_empty_e2e(docker_services, mcp_server_url):
    """Test getting memories for entity with no linked memories"""
    async with Client(mcp_server_url) as client:
        # Create entity with no memory links
        entity_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Entity With No Memories PG',
                'entity_type': 'Individual',
                'tags': ['empty-memory-e2e-pg']
            }
        })
        entity_id = entity_result.data["id"]

        # Get entity memories (should be empty)
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_memories', 'arguments': {
                'entity_id': entity_id
            }
        })

        assert result.data is not None
        assert result.data['count'] == 0
        assert result.data['memory_ids'] == []


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_memories_not_found_e2e(docker_services, mcp_server_url):
    """Test error handling for non-existent entity"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'get_entity_memories', 'arguments': {
                    'entity_id': 999999
                }
            })
            assert False, 'Expected error for non-existent entity'
        except Exception as e:
            assert 'not found' in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_entity_memories_after_unlink_e2e(docker_services, mcp_server_url):
    """Test that unlinking removes memory from entity's memory list"""
    async with Client(mcp_server_url) as client:
        # Create entity
        entity_result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_entity', 'arguments': {
                'name': 'Entity for Unlink Test PG',
                'entity_type': 'Device',
                'tags': ['unlink-memory-e2e-pg']
            }
        })
        entity_id = entity_result.data["id"]

        # Create and link 2 memories
        memory_ids = []
        for i in range(2):
            memory_result = await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'create_memory', 'arguments': {
                    'title': f'Memory for Unlink Test PG {i}',
                    'content': f'Content {i}',
                    'context': 'Testing unlink',
                    'keywords': ['test'],
                    'tags': ['unlink-memory-e2e-pg'],
                    'importance': 7
                }
            })
            memory_ids.append(memory_result.data["id"])
            await client.call_tool('execute_forgetful_tool', {
                'tool_name': 'link_entity_to_memory', 'arguments': {
                    'entity_id': entity_id,
                    'memory_id': memory_result.data["id"]
                }
            })

        # Verify initial state
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_memories', 'arguments': {
                'entity_id': entity_id
            }
        })
        assert result.data['count'] == 2

        # Unlink one memory
        await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'unlink_entity_from_memory', 'arguments': {
                'entity_id': entity_id,
                'memory_id': memory_ids[0]
            }
        })

        # Verify memory was removed
        result = await client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_entity_memories', 'arguments': {
                'entity_id': entity_id
            }
        })
        assert result.data['count'] == 1
        assert memory_ids[1] in result.data['memory_ids']
        assert memory_ids[0] not in result.data['memory_ids']
