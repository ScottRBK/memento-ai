"""E2E tests for Files REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/files endpoints.
"""
import base64

import pytest

# Test data
SMALL_FILE_DATA = base64.b64encode(b"Hello, World!").decode("utf-8")  # 13 bytes
PNG_HEADER = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode("utf-8")


class TestFileAPIList:
    """Test GET /api/v1/files endpoint."""

    @pytest.mark.asyncio
    async def test_list_files_empty(self, http_client):
        """GET /api/v1/files returns empty list initially."""
        response = await http_client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_files_with_data(self, http_client):
        """GET /api/v1/files returns created files."""
        # Create a file first
        payload = {
            "filename": "test.txt",
            "description": "A test text file",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["test"],
        }
        create_response = await http_client.post("/api/v1/files", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_files_filter_mime_type(self, http_client):
        """GET /api/v1/files?mime_type=image/png filters by MIME type."""
        # Create files with different mime types
        await http_client.post("/api/v1/files", json={
            "filename": "document.txt",
            "description": "A text document",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["text"],
        })
        await http_client.post("/api/v1/files", json={
            "filename": "image.png",
            "description": "A PNG image",
            "data": PNG_HEADER,
            "mime_type": "image/png",
            "tags": ["image"],
        })

        # Filter by image/png
        response = await http_client.get("/api/v1/files?mime_type=image/png")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) >= 1
        for file in data["files"]:
            assert file["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_list_files_filter_tags(self, http_client):
        """GET /api/v1/files?tags=unique-file-tag filters by tags."""
        # Create file with specific tag
        await http_client.post("/api/v1/files", json={
            "filename": "tagged-file.txt",
            "description": "A file with a unique tag",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["unique-file-tag"],
        })

        # Filter by tag
        response = await http_client.get("/api/v1/files?tags=unique-file-tag")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) >= 1

    @pytest.mark.asyncio
    async def test_list_files_invalid_project_id(self, http_client):
        """GET /api/v1/files returns 400 for invalid project_id."""
        response = await http_client.get("/api/v1/files?project_id=not_a_number")
        assert response.status_code == 400
        assert "Invalid project_id" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_list_files_excludes_data(self, http_client):
        """GET /api/v1/files returns FileSummary without data field."""
        # Create a file
        await http_client.post("/api/v1/files", json={
            "filename": "summary-check.txt",
            "description": "Check summary fields",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["summary"],
        })

        # List and verify data field is absent
        response = await http_client.get("/api/v1/files")
        assert response.status_code == 200
        data = response.json()
        assert len(data["files"]) >= 1
        for file_summary in data["files"]:
            assert "data" not in file_summary
            # Verify summary fields are present
            assert "id" in file_summary
            assert "filename" in file_summary
            assert "description" in file_summary
            assert "mime_type" in file_summary
            assert "size_bytes" in file_summary
            assert "tags" in file_summary
            assert "created_at" in file_summary
            assert "updated_at" in file_summary


class TestFileAPICrud:
    """Test File CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_file(self, http_client):
        """POST /api/v1/files creates a new file."""
        payload = {
            "filename": "hello.txt",
            "description": "A simple text file",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["test", "hello"],
        }
        response = await http_client.post("/api/v1/files", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["filename"] == "hello.txt"
        assert data["description"] == "A simple text file"
        assert data["mime_type"] == "text/plain"
        assert data["size_bytes"] == 13  # len(b"Hello, World!")
        assert data["tags"] == ["test", "hello"]
        assert data["data"] == SMALL_FILE_DATA
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_create_file_validation_error(self, http_client):
        """POST /api/v1/files returns 400 for invalid data."""
        payload = {
            "filename": "",  # Empty filename should fail
            "mime_type": "text/plain",
        }
        response = await http_client.post("/api/v1/files", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_file(self, http_client):
        """GET /api/v1/files/{id} returns the file with data."""
        # Create first
        create_response = await http_client.post("/api/v1/files", json={
            "filename": "get-test.txt",
            "description": "Testing get endpoint",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["get-test"],
        })
        file_id = create_response.json()["id"]

        # Get
        response = await http_client.get(f"/api/v1/files/{file_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == file_id
        assert data["filename"] == "get-test.txt"
        assert data["data"] == SMALL_FILE_DATA

    @pytest.mark.asyncio
    async def test_get_file_not_found(self, http_client):
        """GET /api/v1/files/{id} returns 404 for missing file."""
        response = await http_client.get("/api/v1/files/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_file(self, http_client):
        """PUT /api/v1/files/{id} updates the file."""
        # Create first
        create_response = await http_client.post("/api/v1/files", json={
            "filename": "update-test.txt",
            "description": "Original description",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["original"],
        })
        file_id = create_response.json()["id"]

        # Update
        new_data = base64.b64encode(b"Updated content!").decode("utf-8")
        update_payload = {
            "filename": "updated-test.txt",
            "description": "Updated description",
            "data": new_data,
            "tags": ["updated"],
        }
        response = await http_client.put(f"/api/v1/files/{file_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "updated-test.txt"
        assert data["description"] == "Updated description"
        assert data["data"] == new_data
        assert data["tags"] == ["updated"]
        assert data["size_bytes"] == len(b"Updated content!")

    @pytest.mark.asyncio
    async def test_update_file_not_found(self, http_client):
        """PUT /api/v1/files/{id} returns 404 for missing file."""
        response = await http_client.put("/api/v1/files/99999", json={"filename": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_file(self, http_client):
        """DELETE /api/v1/files/{id} deletes the file."""
        # Create first
        create_response = await http_client.post("/api/v1/files", json={
            "filename": "delete-test.txt",
            "description": "Will be deleted",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["delete"],
        })
        file_id = create_response.json()["id"]

        # Delete
        response = await http_client.delete(f"/api/v1/files/{file_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/files/{file_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, http_client):
        """DELETE /api/v1/files/{id} returns 404 for missing file."""
        response = await http_client.delete("/api/v1/files/99999")
        assert response.status_code == 404


class TestFileMemoryLinking:
    """Test linking files to memories."""

    @pytest.mark.asyncio
    async def test_create_memory_with_file_ids(self, http_client):
        """POST /api/v1/memories with file_ids links files to memory."""
        # Create a file first
        file_response = await http_client.post("/api/v1/files", json={
            "filename": "linked-file.png",
            "description": "File to link to memory",
            "data": PNG_HEADER,
            "mime_type": "image/png",
            "tags": ["linked"],
        })
        assert file_response.status_code == 201
        file_id = file_response.json()["id"]

        # Create a memory with file_ids
        memory_payload = {
            "title": "Memory with file attachment",
            "content": "This memory has an attached image file.",
            "context": "Testing file-memory linking",
            "keywords": ["file", "link"],
            "tags": ["test"],
            "importance": 7,
            "file_ids": [file_id],
        }
        memory_response = await http_client.post("/api/v1/memories", json=memory_payload)
        assert memory_response.status_code == 201
        memory_id = memory_response.json()["id"]

        # Verify linking via GET (returns full Memory model with file_ids)
        get_response = await http_client.get(f"/api/v1/memories/{memory_id}")
        assert get_response.status_code == 200
        memory_data = get_response.json()
        assert file_id in memory_data.get("file_ids", [])
