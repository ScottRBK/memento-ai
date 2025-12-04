"""
E2E tests for Code Artifact REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/code-artifacts endpoints.
"""
import pytest


class TestCodeArtifactAPIList:
    """Test GET /api/v1/code-artifacts endpoint."""

    @pytest.mark.asyncio
    async def test_list_code_artifacts_empty(self, http_client):
        """GET /api/v1/code-artifacts returns empty list initially."""
        response = await http_client.get("/api/v1/code-artifacts")
        assert response.status_code == 200
        data = response.json()
        assert data["code_artifacts"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_code_artifacts_with_data(self, http_client):
        """GET /api/v1/code-artifacts returns created artifacts."""
        # Create an artifact first
        payload = {
            "title": "Test Code Artifact",
            "description": "A test code snippet",
            "code": "def hello():\n    return 'Hello, World!'",
            "language": "python",
            "tags": ["test"]
        }
        create_response = await http_client.post("/api/v1/code-artifacts", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/code-artifacts")
        assert response.status_code == 200
        data = response.json()
        assert len(data["code_artifacts"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_code_artifacts_filter_by_language(self, http_client):
        """GET /api/v1/code-artifacts filters by language."""
        # Create artifacts with different languages
        await http_client.post("/api/v1/code-artifacts", json={
            "title": "Python Artifact",
            "description": "A Python snippet",
            "code": "print('Hello')",
            "language": "python",
            "tags": ["python"]
        })
        await http_client.post("/api/v1/code-artifacts", json={
            "title": "JavaScript Artifact",
            "description": "A JavaScript snippet",
            "code": "console.log('Hello')",
            "language": "javascript",
            "tags": ["javascript"]
        })

        # Filter by python
        response = await http_client.get("/api/v1/code-artifacts?language=python")
        assert response.status_code == 200
        data = response.json()
        for artifact in data["code_artifacts"]:
            assert artifact["language"] == "python"

    @pytest.mark.asyncio
    async def test_list_code_artifacts_filter_by_tags(self, http_client):
        """GET /api/v1/code-artifacts filters by tags."""
        # Create artifact with specific tag
        await http_client.post("/api/v1/code-artifacts", json={
            "title": "Tagged Artifact",
            "description": "A tagged snippet",
            "code": "# special code",
            "language": "python",
            "tags": ["special-artifact-tag"]
        })

        # Filter by tag
        response = await http_client.get("/api/v1/code-artifacts?tags=special-artifact-tag")
        assert response.status_code == 200
        data = response.json()
        assert len(data["code_artifacts"]) >= 1

    @pytest.mark.asyncio
    async def test_list_code_artifacts_invalid_project_id(self, http_client):
        """GET /api/v1/code-artifacts returns 400 for invalid project_id."""
        response = await http_client.get("/api/v1/code-artifacts?project_id=not_a_number")
        assert response.status_code == 400
        assert "Invalid project_id" in response.json()["error"]


class TestCodeArtifactAPICrud:
    """Test Code Artifact CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_code_artifact(self, http_client):
        """POST /api/v1/code-artifacts creates a new artifact."""
        payload = {
            "title": "New Code Artifact",
            "description": "A new code snippet",
            "code": "function greet() {\n  return 'Hello';\n}",
            "language": "javascript",
            "tags": ["new", "artifact"]
        }
        response = await http_client.post("/api/v1/code-artifacts", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["title"] == "New Code Artifact"
        assert data["language"] == "javascript"

    @pytest.mark.asyncio
    async def test_create_code_artifact_validation_error(self, http_client):
        """POST /api/v1/code-artifacts returns 400 for invalid data."""
        payload = {
            "title": "",  # Empty title should fail
            "language": "python"
        }
        response = await http_client.post("/api/v1/code-artifacts", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_code_artifact(self, http_client):
        """GET /api/v1/code-artifacts/{id} returns the artifact."""
        # Create first
        create_response = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Get Test Artifact",
            "description": "Testing get endpoint",
            "code": "SELECT * FROM users;",
            "language": "sql",
            "tags": ["test"]
        })
        artifact_id = create_response.json()["id"]

        # Get
        response = await http_client.get(f"/api/v1/code-artifacts/{artifact_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == artifact_id
        assert data["title"] == "Get Test Artifact"

    @pytest.mark.asyncio
    async def test_get_code_artifact_not_found(self, http_client):
        """GET /api/v1/code-artifacts/{id} returns 404 for missing artifact."""
        response = await http_client.get("/api/v1/code-artifacts/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_code_artifact(self, http_client):
        """PUT /api/v1/code-artifacts/{id} updates the artifact."""
        # Create first
        create_response = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Update Test Artifact",
            "description": "Original description",
            "code": "# Original code",
            "language": "python",
            "tags": ["original"]
        })
        artifact_id = create_response.json()["id"]

        # Update
        update_payload = {
            "title": "Updated Artifact Title",
            "description": "Updated description",
            "code": "# Updated code\nprint('Updated!')",
            "tags": ["updated"]
        }
        response = await http_client.put(f"/api/v1/code-artifacts/{artifact_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Artifact Title"
        assert data["description"] == "Updated description"
        assert "Updated" in data["code"]

    @pytest.mark.asyncio
    async def test_update_code_artifact_not_found(self, http_client):
        """PUT /api/v1/code-artifacts/{id} returns 404 for missing artifact."""
        response = await http_client.put("/api/v1/code-artifacts/99999", json={"title": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_code_artifact(self, http_client):
        """DELETE /api/v1/code-artifacts/{id} deletes the artifact."""
        # Create first
        create_response = await http_client.post("/api/v1/code-artifacts", json={
            "title": "Delete Test Artifact",
            "description": "Will be deleted",
            "code": "# Will be deleted",
            "language": "python",
            "tags": ["delete"]
        })
        artifact_id = create_response.json()["id"]

        # Delete
        response = await http_client.delete(f"/api/v1/code-artifacts/{artifact_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/code-artifacts/{artifact_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_code_artifact_not_found(self, http_client):
        """DELETE /api/v1/code-artifacts/{id} returns 404 for missing artifact."""
        response = await http_client.delete("/api/v1/code-artifacts/99999")
        assert response.status_code == 404


class TestCodeArtifactLanguages:
    """Test different programming languages."""

    @pytest.mark.asyncio
    async def test_create_artifact_various_languages(self, http_client):
        """POST /api/v1/code-artifacts supports various languages."""
        languages = ["python", "javascript", "typescript", "rust", "go", "java", "sql", "bash", "yaml", "json"]

        for lang in languages:
            response = await http_client.post("/api/v1/code-artifacts", json={
                "title": f"Artifact in {lang}",
                "description": f"Testing {lang} language",
                "code": f"// Code in {lang}",
                "language": lang,
                "tags": [lang]
            })
            assert response.status_code == 201, f"Failed for language: {lang}"
            assert response.json()["language"] == lang
