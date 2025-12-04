"""
E2E tests for Document REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/documents endpoints.
"""
import pytest


class TestDocumentAPIList:
    """Test GET /api/v1/documents endpoint."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, http_client):
        """GET /api/v1/documents returns empty list initially."""
        response = await http_client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_documents_with_data(self, http_client):
        """GET /api/v1/documents returns created documents."""
        # Create a document first
        payload = {
            "title": "Test Document",
            "description": "A test document",
            "content": "This is the document content with enough text to be valid.",
            "document_type": "analysis",
            "tags": ["test"]
        }
        create_response = await http_client.post("/api/v1/documents", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_type(self, http_client):
        """GET /api/v1/documents filters by document_type."""
        # Create documents of different types
        await http_client.post("/api/v1/documents", json={
            "title": "Analysis Document",
            "description": "An analysis document",
            "content": "Analysis content here with enough text.",
            "document_type": "analysis",
            "tags": ["analysis"]
        })
        await http_client.post("/api/v1/documents", json={
            "title": "Guide Document",
            "description": "A guide document",
            "content": "Guide content here with enough text.",
            "document_type": "guide",
            "tags": ["guide"]
        })

        # Filter by analysis
        response = await http_client.get("/api/v1/documents?document_type=analysis")
        assert response.status_code == 200
        data = response.json()
        for doc in data["documents"]:
            assert doc["document_type"] == "analysis"

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_tags(self, http_client):
        """GET /api/v1/documents filters by tags."""
        # Create documents with different tags
        await http_client.post("/api/v1/documents", json={
            "title": "Tagged Document",
            "description": "A tagged document",
            "content": "Content for tagged document test.",
            "document_type": "specification",
            "tags": ["special-tag"]
        })

        # Filter by tag
        response = await http_client.get("/api/v1/documents?tags=special-tag")
        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) >= 1


class TestDocumentAPICrud:
    """Test Document CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_document(self, http_client):
        """POST /api/v1/documents creates a new document."""
        payload = {
            "title": "New Document",
            "description": "A new document",
            "content": "This is the content of the new document.",
            "document_type": "analysis",
            "tags": ["new", "document"]
        }
        response = await http_client.post("/api/v1/documents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["title"] == "New Document"
        assert data["document_type"] == "analysis"

    @pytest.mark.asyncio
    async def test_create_document_validation_error(self, http_client):
        """POST /api/v1/documents returns 400 for invalid data."""
        payload = {
            "title": "",  # Empty title should fail
            "document_type": "analysis"
        }
        response = await http_client.post("/api/v1/documents", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_document(self, http_client):
        """GET /api/v1/documents/{id} returns the document."""
        # Create first
        create_response = await http_client.post("/api/v1/documents", json={
            "title": "Get Test Document",
            "description": "Testing get endpoint",
            "content": "Content for getting the document.",
            "document_type": "guide",
            "tags": ["test"]
        })
        document_id = create_response.json()["id"]

        # Get
        response = await http_client.get(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document_id
        assert data["title"] == "Get Test Document"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, http_client):
        """GET /api/v1/documents/{id} returns 404 for missing document."""
        response = await http_client.get("/api/v1/documents/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_document(self, http_client):
        """PUT /api/v1/documents/{id} updates the document."""
        # Create first
        create_response = await http_client.post("/api/v1/documents", json={
            "title": "Update Test Document",
            "description": "Original description",
            "content": "Original content for the document.",
            "document_type": "specification",
            "tags": ["original"]
        })
        document_id = create_response.json()["id"]

        # Update
        update_payload = {
            "title": "Updated Document Title",
            "description": "Updated description",
            "tags": ["updated"]
        }
        response = await http_client.put(f"/api/v1/documents/{document_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Document Title"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_document_not_found(self, http_client):
        """PUT /api/v1/documents/{id} returns 404 for missing document."""
        response = await http_client.put("/api/v1/documents/99999", json={"title": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_document(self, http_client):
        """DELETE /api/v1/documents/{id} deletes the document."""
        # Create first
        create_response = await http_client.post("/api/v1/documents", json={
            "title": "Delete Test Document",
            "description": "Will be deleted",
            "content": "Content that will be deleted.",
            "document_type": "note",
            "tags": ["delete"]
        })
        document_id = create_response.json()["id"]

        # Delete
        response = await http_client.delete(f"/api/v1/documents/{document_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/documents/{document_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, http_client):
        """DELETE /api/v1/documents/{id} returns 404 for missing document."""
        response = await http_client.delete("/api/v1/documents/99999")
        assert response.status_code == 404


class TestDocumentTypes:
    """Test different document types."""

    @pytest.mark.asyncio
    async def test_create_document_all_types(self, http_client):
        """POST /api/v1/documents supports various document types."""
        document_types = ["analysis", "guide", "specification", "report", "note", "reference"]

        for dtype in document_types:
            response = await http_client.post("/api/v1/documents", json={
                "title": f"Document Type {dtype}",
                "description": f"Testing {dtype} type",
                "content": f"Content for {dtype} document type test.",
                "document_type": dtype,
                "tags": [dtype]
            })
            assert response.status_code == 201, f"Failed for type: {dtype}"
            assert response.json()["document_type"] == dtype
