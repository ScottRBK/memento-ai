"""E2E tests for Skill REST API endpoints.

Uses in-memory SQLite for test isolation.
Tests the /api/v1/skills endpoints.
"""
import pytest


class TestSkillAPIList:
    """Test GET /api/v1/skills endpoint."""

    @pytest.mark.asyncio
    async def test_list_skills_empty(self, http_client):
        """GET /api/v1/skills returns empty list initially."""
        response = await http_client.get("/api/v1/skills")
        assert response.status_code == 200
        data = response.json()
        assert data["skills"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_skills_with_data(self, http_client):
        """GET /api/v1/skills returns created skills."""
        payload = {
            "name": "list-test-skill",
            "description": "A test skill for listing",
            "content": "# List Test\n\nSteps here.",
            "tags": ["test"],
            "importance": 7,
        }
        create_response = await http_client.post("/api/v1/skills", json=payload)
        assert create_response.status_code == 201

        response = await http_client.get("/api/v1/skills")
        assert response.status_code == 200
        data = response.json()
        assert len(data["skills"]) >= 1
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_skills_filter_by_tags(self, http_client):
        """GET /api/v1/skills filters by tags."""
        await http_client.post("/api/v1/skills", json={
            "name": "tagged-api-skill",
            "description": "Skill with special tag",
            "content": "Content for tagged skill.",
            "tags": ["special-api-tag"],
            "importance": 7,
        })

        response = await http_client.get("/api/v1/skills?tags=special-api-tag")
        assert response.status_code == 200
        data = response.json()
        assert len(data["skills"]) >= 1

    @pytest.mark.asyncio
    async def test_list_skills_invalid_project_id(self, http_client):
        """GET /api/v1/skills returns 400 for invalid project_id."""
        response = await http_client.get("/api/v1/skills?project_id=not_a_number")
        assert response.status_code == 400
        assert "Invalid project_id" in response.json()["error"]


class TestSkillAPICrud:
    """Test Skill CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_skill_api(self, http_client):
        """POST /api/v1/skills creates a new skill."""
        payload = {
            "name": "api-create-skill",
            "description": "A skill created via REST API",
            "content": "# API Skill\n\n## Steps\n1. First step",
            "tags": ["api", "create"],
            "importance": 8,
        }
        response = await http_client.post("/api/v1/skills", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] > 0
        assert data["name"] == "api-create-skill"
        assert data["description"] == "A skill created via REST API"
        assert data["importance"] == 8

    @pytest.mark.asyncio
    async def test_create_skill_validation_error(self, http_client):
        """POST /api/v1/skills returns 400 for invalid data."""
        payload = {
            "name": "InvalidUpperCase",
            "description": "Should fail validation",
            "content": "Content",
        }
        response = await http_client.post("/api/v1/skills", json=payload)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_skill_api(self, http_client):
        """GET /api/v1/skills/{id} returns the skill."""
        create_response = await http_client.post("/api/v1/skills", json={
            "name": "get-api-skill",
            "description": "Testing get endpoint",
            "content": "Content for getting the skill.",
            "tags": ["test"],
            "importance": 7,
        })
        skill_id = create_response.json()["id"]

        response = await http_client.get(f"/api/v1/skills/{skill_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == skill_id
        assert data["name"] == "get-api-skill"

    @pytest.mark.asyncio
    async def test_get_skill_not_found(self, http_client):
        """GET /api/v1/skills/{id} returns 404 for missing skill."""
        response = await http_client.get("/api/v1/skills/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_skill_api(self, http_client):
        """PUT /api/v1/skills/{id} updates the skill."""
        create_response = await http_client.post("/api/v1/skills", json={
            "name": "update-api-skill",
            "description": "Original description",
            "content": "Original content for the skill.",
            "tags": ["original"],
            "importance": 7,
        })
        skill_id = create_response.json()["id"]

        update_payload = {
            "description": "Updated description via API",
            "tags": ["updated"],
        }
        response = await http_client.put(f"/api/v1/skills/{skill_id}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description via API"

    @pytest.mark.asyncio
    async def test_update_skill_not_found(self, http_client):
        """PUT /api/v1/skills/{id} returns 404 for missing skill."""
        response = await http_client.put("/api/v1/skills/99999", json={"description": "Test"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_skill_api(self, http_client):
        """DELETE /api/v1/skills/{id} deletes the skill."""
        create_response = await http_client.post("/api/v1/skills", json={
            "name": "delete-api-skill",
            "description": "Will be deleted",
            "content": "Content that will be deleted.",
            "tags": ["delete"],
            "importance": 7,
        })
        skill_id = create_response.json()["id"]

        response = await http_client.delete(f"/api/v1/skills/{skill_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify deleted
        get_response = await http_client.get(f"/api/v1/skills/{skill_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_skill_not_found(self, http_client):
        """DELETE /api/v1/skills/{id} returns 404 for missing skill."""
        response = await http_client.delete("/api/v1/skills/99999")
        assert response.status_code == 404


class TestSkillAPISearch:
    """Test GET /api/v1/skills/search endpoint."""

    @pytest.mark.asyncio
    async def test_search_skills_api(self, http_client):
        """GET /api/v1/skills/search returns matching skills."""
        await http_client.post("/api/v1/skills", json={
            "name": "search-api-deploy",
            "description": "Deploy application to production using Docker containers",
            "content": "# Deploy\n\n## Steps\n1. Build image\n2. Push to registry",
            "tags": ["deployment"],
            "importance": 8,
        })

        response = await http_client.get("/api/v1/skills/search?query=deploy+docker+production")
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert "total" in data
        assert len(data["skills"]) >= 1

    @pytest.mark.asyncio
    async def test_search_skills_missing_query(self, http_client):
        """GET /api/v1/skills/search returns 400 without query param."""
        response = await http_client.get("/api/v1/skills/search")
        assert response.status_code == 400
        assert "query" in response.json()["error"].lower()


class TestSkillAPIImportExport:
    """Test import/export endpoints."""

    @pytest.mark.asyncio
    async def test_import_skill_api(self, http_client):
        """POST /api/v1/skills/import creates skill from SKILL.md format."""
        skill_md = """---
name: api-imported-skill
description: Imported via REST API
license: MIT
allowed-tools:
  - Read
  - Grep
---

# API Imported Skill

## Steps
1. First step
2. Second step
"""
        response = await http_client.post("/api/v1/skills/import", json={
            "skill_md": skill_md,
            "importance": 8,
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api-imported-skill"
        assert data["description"] == "Imported via REST API"
        assert data["license"] == "MIT"
        assert data["importance"] == 8

    @pytest.mark.asyncio
    async def test_export_skill_api(self, http_client):
        """GET /api/v1/skills/{id}/export returns SKILL.md format."""
        create_response = await http_client.post("/api/v1/skills", json={
            "name": "api-export-skill",
            "description": "Skill for export via API",
            "content": "# Export\n\n## Steps\n1. Export step",
            "license": "Apache-2.0",
            "tags": ["export"],
            "importance": 7,
        })
        skill_id = create_response.json()["id"]

        response = await http_client.get(f"/api/v1/skills/{skill_id}/export")
        assert response.status_code == 200
        data = response.json()
        assert "skill_md" in data
        skill_md = data["skill_md"]
        assert "---" in skill_md
        assert "name: api-export-skill" in skill_md
        assert "# Export" in skill_md

    @pytest.mark.asyncio
    async def test_export_skill_not_found(self, http_client):
        """GET /api/v1/skills/{id}/export returns 404 for missing skill."""
        response = await http_client.get("/api/v1/skills/99999/export")
        assert response.status_code == 404
