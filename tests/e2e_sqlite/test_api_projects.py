"""
E2E tests for Project REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/projects endpoints.
"""
import pytest


class TestProjectAPIList:
    """Test GET /api/v1/projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, http_client):
        """GET /api/v1/projects returns empty list initially."""
        response = await http_client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_projects_with_data(self, http_client):
        """GET /api/v1/projects returns created projects."""
        # Create a project first
        payload = {
            "name": "Test Project",
            "description": "A test project",
            "project_type": "development"
        }
        create_response = await http_client.post("/api/v1/projects", json=payload)
        assert create_response.status_code == 201

        # Now list
        response = await http_client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_projects_filter_by_status(self, http_client):
        """GET /api/v1/projects filters by status."""
        # Create projects with different statuses
        await http_client.post("/api/v1/projects", json={
            "name": "Active Project",
            "description": "An active project",
            "project_type": "development",
            "status": "active"
        })

        # Filter by active status
        response = await http_client.get("/api/v1/projects?status=active")
        assert response.status_code == 200
        data = response.json()
        for project in data["projects"]:
            assert project["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_projects_invalid_status(self, http_client):
        """GET /api/v1/projects returns 400 for invalid status."""
        response = await http_client.get("/api/v1/projects?status=invalid")
        assert response.status_code == 400


class TestProjectAPICrud:
    """Test Project CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_project(self, http_client):
        """POST /api/v1/projects creates a new project."""
        payload = {
            "name": "New Project",
            "description": "A new development project",
            "project_type": "development"
        }
        response = await http_client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["name"] == "New Project"
        assert data["project_type"] == "development"
        assert data["status"] == "active"  # Default status

    @pytest.mark.asyncio
    async def test_create_project_with_repo_name(self, http_client):
        """POST /api/v1/projects creates project with repo_name."""
        payload = {
            "name": "GitHub Project",
            "description": "A project linked to GitHub",
            "project_type": "open-source",
            "repo_name": "owner/repo"
        }
        response = await http_client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["repo_name"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_create_project_validation_error(self, http_client):
        """POST /api/v1/projects returns 400 for invalid data."""
        payload = {
            "name": "",  # Empty name should fail
            "project_type": "development"
        }
        response = await http_client.post("/api/v1/projects", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_project(self, http_client):
        """GET /api/v1/projects/{id} returns the project."""
        # Create first
        create_response = await http_client.post("/api/v1/projects", json={
            "name": "Get Test Project",
            "description": "Testing get endpoint",
            "project_type": "documentation"
        })
        project_id = create_response.json()["id"]

        # Get
        response = await http_client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Get Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, http_client):
        """GET /api/v1/projects/{id} returns 404 for missing project."""
        response = await http_client.get("/api/v1/projects/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_project(self, http_client):
        """PUT /api/v1/projects/{id} updates the project."""
        # Create first
        create_response = await http_client.post("/api/v1/projects", json={
            "name": "Update Test Project",
            "description": "Original description",
            "project_type": "development"
        })
        project_id = create_response.json()["id"]

        # Update
        update_payload = {
            "name": "Updated Project Name",
            "description": "Updated description",
            "status": "completed"
        }
        response = await http_client.put(f"/api/v1/projects/{project_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Project Name"
        assert data["description"] == "Updated description"
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, http_client):
        """PUT /api/v1/projects/{id} returns 404 for missing project."""
        response = await http_client.put("/api/v1/projects/99999", json={"name": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project(self, http_client):
        """DELETE /api/v1/projects/{id} deletes the project."""
        # Create first
        create_response = await http_client.post("/api/v1/projects", json={
            "name": "Delete Test Project",
            "description": "Will be deleted",
            "project_type": "infrastructure"
        })
        project_id = create_response.json()["id"]

        # Delete
        response = await http_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, http_client):
        """DELETE /api/v1/projects/{id} returns 404 for missing project."""
        response = await http_client.delete("/api/v1/projects/99999")
        assert response.status_code == 404


class TestProjectTypes:
    """Test different project types."""

    @pytest.mark.asyncio
    async def test_create_project_all_types(self, http_client):
        """POST /api/v1/projects supports all project types."""
        project_types = ["personal", "work", "learning", "development", "infrastructure", "template", "product", "documentation", "open-source"]

        for ptype in project_types:
            response = await http_client.post("/api/v1/projects", json={
                "name": f"Project Type {ptype}",
                "description": f"Testing {ptype} type",
                "project_type": ptype
            })
            assert response.status_code == 201, f"Failed for type: {ptype}"
            assert response.json()["project_type"] == ptype
