"""
E2E tests for document MCP tools with real PostgreSQL database
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_document_basic_e2e(docker_services, mcp_server_url):
    """Test creating a document with all fields"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("create_document", {
            "title": "API Documentation",
            "description": "REST API documentation for the service",
            "content": "# API Documentation\n\n## Endpoints\n\n### GET /api/v1/items\n\nReturns a list of items...",
            "document_type": "markdown",
            "filename": "api-docs.md",
            "tags": ["api", "documentation", "rest"]
        })

        assert result.data is not None
        assert result.data.id is not None
        assert result.data.title == "API Documentation"
        assert result.data.description == "REST API documentation for the service"
        assert result.data.document_type == "markdown"
        assert result.data.filename == "api-docs.md"
        assert result.data.tags == ["api", "documentation", "rest"]
        assert result.data.size_bytes is not None
        assert result.data.size_bytes > 0
        assert result.data.created_at is not None
        assert result.data.updated_at is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_document_e2e(docker_services, mcp_server_url):
    """Test creating then retrieving a document"""
    async with Client(mcp_server_url) as client:
        # Create document
        create_result = await client.call_tool("create_document", {
            "title": "Test Document",
            "description": "Test document for retrieval",
            "content": "This is the document content for testing retrieval.",
            "document_type": "text",
            "tags": ["test"]
        })

        document_id = create_result.data.id

        # Get document
        get_result = await client.call_tool("get_document", {
            "document_id": document_id
        })

        assert get_result.data is not None
        assert get_result.data.id == document_id
        assert get_result.data.title == "Test Document"
        assert get_result.data.content == "This is the document content for testing retrieval."


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_documents_e2e(docker_services, mcp_server_url):
    """Test listing documents"""
    async with Client(mcp_server_url) as client:
        # Create multiple documents
        document_titles = ["doc-list-1", "doc-list-2", "doc-list-3"]

        for title in document_titles:
            await client.call_tool("create_document", {
                "title": title,
                "description": f"Description for {title}",
                "content": f"Content for {title}",
                "document_type": "text",
                "tags": ["list-test"]
            })

        # List all documents
        list_result = await client.call_tool("list_documents", {})

        assert list_result.data is not None
        assert "documents" in list_result.data
        assert "total_count" in list_result.data

        documents = list_result.data["documents"]
        assert len(documents) >= 3

        # Verify our documents are in the list
        document_titles_in_result = [d["title"] for d in documents]
        for title in document_titles:
            assert title in document_titles_in_result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_documents_by_project_e2e(docker_services, mcp_server_url):
    """Test filtering documents by project_id"""
    async with Client(mcp_server_url) as client:
        # Create a project
        project_result = await client.call_tool("create_project", {
            "name": "document-test-project",
            "description": "Project for document filtering",
            "project_type": "development"
        })
        project_id = project_result.data.id

        # Create document without project
        await client.call_tool("create_document", {
            "title": "Unlinked Document",
            "description": "Not linked to project",
            "content": "No project association",
            "document_type": "text",
            "tags": []
        })

        # Create document with project
        create_result = await client.call_tool("create_document", {
            "title": "Linked Document",
            "description": "Linked to project",
            "content": "Has project association",
            "document_type": "text",
            "tags": []
        })
        document_id = create_result.data.id

        # Link to project via update
        await client.call_tool("update_document", {
            "document_id": document_id,
            "project_id": project_id
        })

        # List documents filtered by project
        list_result = await client.call_tool("list_documents", {
            "project_id": project_id
        })

        documents = list_result.data["documents"]
        assert len(documents) == 1
        assert documents[0]["title"] == "Linked Document"
        assert documents[0]["project_id"] == project_id


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_document_e2e(docker_services, mcp_server_url):
    """Test updating a document (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create document
        create_result = await client.call_tool("create_document", {
            "title": "Original Title",
            "description": "Original description",
            "content": "Original content",
            "document_type": "text",
            "tags": ["original"]
        })

        document_id = create_result.data.id

        # Update only title and content
        update_result = await client.call_tool("update_document", {
            "document_id": document_id,
            "title": "Updated Title",
            "content": "Updated content here"
        })

        assert update_result.data.title == "Updated Title"
        assert update_result.data.description == "Original description"  # Unchanged
        assert update_result.data.content == "Updated content here"
        assert update_result.data.tags == ["original"]  # Unchanged


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_document_e2e(docker_services, mcp_server_url):
    """Test deleting a document"""
    async with Client(mcp_server_url) as client:
        # Create document
        create_result = await client.call_tool("create_document", {
            "title": "To Delete",
            "description": "Will be deleted",
            "content": "Delete this document",
            "document_type": "text",
            "tags": []
        })

        document_id = create_result.data.id

        # Delete document
        delete_result = await client.call_tool("delete_document", {
            "document_id": document_id
        })

        assert delete_result.data is not None
        assert delete_result.data["deleted_id"] == document_id

        # Verify document is gone
        try:
            await client.call_tool("get_document", {
                "document_id": document_id
            })
            assert False, "Expected error for deleted document"
        except Exception as e:
            assert "not found" in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_document_not_found_e2e(docker_services, mcp_server_url):
    """Test error handling for non-existent document"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("get_document", {
                "document_id": 999999
            })
            assert False, "Expected error for non-existent document"
        except Exception as e:
            assert "not found" in str(e).lower()
