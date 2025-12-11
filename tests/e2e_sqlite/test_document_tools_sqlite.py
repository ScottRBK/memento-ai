"""
E2E tests for document MCP tools with sqlite-backed MCP server
"""
import pytest


@pytest.mark.asyncio
async def test_create_document_basic_e2e(mcp_client):
    """Test creating a document with all fields"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'API Documentation',
            'description': 'REST API documentation for the service',
            'content': """# API Documentation

## Endpoints

### GET /api/v1/items

Returns a list of items...""",
            'document_type': 'markdown',
            'filename': 'api-docs.md',
            'tags': ['api', 'documentation', 'rest'],
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["title"] == 'API Documentation'
    assert result.data["description"] == 'REST API documentation for the service'
    assert result.data["document_type"] == 'markdown'
    assert result.data["filename"] == 'api-docs.md'
    assert result.data["tags"] == ['api', 'documentation', 'rest']
    assert result.data["size_bytes"] is not None
    assert result.data["size_bytes"] > 0
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.asyncio
async def test_get_document_e2e(mcp_client):
    """Test creating then retrieving a document"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'Test Document',
            'description': 'Test document for retrieval',
            'content': 'This is the document content for testing retrieval.',
            'document_type': 'text',
            'tags': ['test'],
        },
    })
    document_id = create_result.data["id"]
    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_document',
        'arguments': {'document_id': document_id},
    })
    assert get_result.data is not None
    assert get_result.data["id"] == document_id
    assert get_result.data["title"] == 'Test Document'
    assert get_result.data["content"] == 'This is the document content for testing retrieval.'


@pytest.mark.asyncio
async def test_list_documents_e2e(mcp_client):
    """Test listing documents"""
    document_titles = ['doc-list-1', 'doc-list-2', 'doc-list-3']
    for title in document_titles:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_document',
            'arguments': {
                'title': title,
                'description': f'Description for {title}',
                'content': f'Content for {title}',
                'document_type': 'text',
                'tags': ['list-test'],
            },
        })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_documents',
        'arguments': {},
    })
    assert list_result.data is not None
    assert 'documents' in list_result.data
    assert 'total_count' in list_result.data
    documents = list_result.data['documents']
    assert len(documents) >= 3
    document_titles_in_result = [d['title'] for d in documents]
    for title in document_titles:
        assert title in document_titles_in_result


@pytest.mark.asyncio
async def test_list_documents_by_project_e2e(mcp_client):
    """Test filtering documents by project_id"""
    project_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_project',
        'arguments': {
            'name': 'document-test-project',
            'description': 'Project for document filtering',
            'project_type': 'development',
        },
    })
    project_id = project_result.data["id"]

    # Unlinked document
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'Unlinked Document',
            'description': 'Not linked to project',
            'content': 'No project association',
            'document_type': 'text',
            'tags': [],
        },
    })

    # Linked document
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'Linked Document',
            'description': 'Linked to project',
            'content': 'Has project association',
            'document_type': 'text',
            'tags': [],
        },
    })
    document_id = create_result.data["id"]

    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_document',
        'arguments': {
            'document_id': document_id,
            'project_id': project_id,
        },
    })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_documents',
        'arguments': {'project_id': project_id},
    })
    documents = list_result.data['documents']
    assert len(documents) == 1
    assert documents[0]['title'] == 'Linked Document'
    assert documents[0]['project_id'] == project_id


@pytest.mark.asyncio
async def test_update_document_e2e(mcp_client):
    """Test updating a document (PATCH semantics)"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'Original Title',
            'description': 'Original description',
            'content': 'Original content',
            'document_type': 'text',
            'tags': ['original'],
        },
    })
    document_id = create_result.data["id"]

    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_document',
        'arguments': {
            'document_id': document_id,
            'title': 'Updated Title',
            'content': 'Updated content here',
        },
    })
    assert update_result.data["title"] == 'Updated Title'
    assert update_result.data["description"] == 'Original description'
    assert update_result.data["content"] == 'Updated content here'
    assert update_result.data["tags"] == ['original']


@pytest.mark.asyncio
async def test_delete_document_e2e(mcp_client):
    """Test deleting a document"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'To Delete',
            'description': 'Will be deleted',
            'content': 'Delete this document',
            'document_type': 'text',
            'tags': [],
        },
    })
    document_id = create_result.data["id"]

    delete_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'delete_document',
        'arguments': {'document_id': document_id},
    })
    assert delete_result.data is not None
    assert delete_result.data['deleted_id'] == document_id

    try:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_document',
            'arguments': {'document_id': document_id},
        })
        assert False, 'Expected error for deleted document'
    except Exception as e:
        assert 'not found' in str(e).lower()


@pytest.mark.asyncio
async def test_get_document_not_found_e2e(mcp_client):
    """Test error handling for non-existent document"""
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_document',
            'arguments': {'document_id': 999999},
        })
        assert False, 'Expected error for non-existent document'
    except Exception as e:
        assert 'not found' in str(e).lower()


@pytest.mark.asyncio
async def test_create_document_without_tags_e2e(mcp_client):
    """Test creating document without providing tags parameter (GitHub issue #4)"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_document',
        'arguments': {
            'title': 'No Tags Document',
            'description': 'Document created without tags parameter',
            'content': 'This document omits the tags field entirely.',
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["title"] == 'No Tags Document'
    assert result.data["tags"] == []  # Should default to empty list
