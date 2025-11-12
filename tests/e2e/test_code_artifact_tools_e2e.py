"""
E2E tests for code artifact MCP tools with real PostgreSQL database
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_code_artifact_basic_e2e(docker_services, mcp_server_url):
    """Test creating a code artifact with all fields"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("create_code_artifact", {
            "title": "JWT Middleware",
            "description": "FastAPI JWT validation middleware",
            "code": "@app.middleware('http')\nasync def jwt_middleware(request, call_next):\n    return await call_next(request)",
            "language": "python",
            "tags": ["fastapi", "auth", "middleware"]
        })

        assert result.data is not None
        assert result.data.id is not None
        assert result.data.title == "JWT Middleware"
        assert result.data.description == "FastAPI JWT validation middleware"
        assert result.data.language == "python"
        assert result.data.tags == ["fastapi", "auth", "middleware"]
        assert result.data.created_at is not None
        assert result.data.updated_at is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_code_artifact_e2e(docker_services, mcp_server_url):
    """Test creating then retrieving a code artifact"""
    async with Client(mcp_server_url) as client:
        # Create artifact
        create_result = await client.call_tool("create_code_artifact", {
            "title": "Test Artifact",
            "description": "Test artifact for retrieval",
            "code": "print('hello world')",
            "language": "python",
            "tags": ["test"]
        })

        artifact_id = create_result.data.id

        # Get artifact
        get_result = await client.call_tool("get_code_artifact", {
            "artifact_id": artifact_id
        })

        assert get_result.data is not None
        assert get_result.data.id == artifact_id
        assert get_result.data.title == "Test Artifact"
        assert get_result.data.code == "print('hello world')"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_code_artifacts_e2e(docker_services, mcp_server_url):
    """Test listing code artifacts"""
    async with Client(mcp_server_url) as client:
        # Create multiple artifacts
        artifact_titles = ["list-test-1", "list-test-2", "list-test-3"]

        for title in artifact_titles:
            await client.call_tool("create_code_artifact", {
                "title": title,
                "description": f"Description for {title}",
                "code": f"# Code for {title}",
                "language": "python",
                "tags": ["list-test"]
            })

        # List all artifacts
        list_result = await client.call_tool("list_code_artifacts", {})

        assert list_result.data is not None
        assert "code_artifacts" in list_result.data
        assert "total_count" in list_result.data

        artifacts = list_result.data["code_artifacts"]
        assert len(artifacts) >= 3

        # Verify our artifacts are in the list
        artifact_titles_in_result = [a["title"] for a in artifacts]
        for title in artifact_titles:
            assert title in artifact_titles_in_result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_code_artifacts_by_project_e2e(docker_services, mcp_server_url):
    """Test filtering code artifacts by project_id"""
    async with Client(mcp_server_url) as client:
        # Create a project
        project_result = await client.call_tool("create_project", {
            "name": "artifact-test-project",
            "description": "Project for artifact filtering",
            "project_type": "development"
        })
        project_id = project_result.data.id

        # Create artifact without project
        await client.call_tool("create_code_artifact", {
            "title": "Unlinked Artifact",
            "description": "Not linked to project",
            "code": "# No project",
            "language": "python",
            "tags": []
        })

        # Create artifact with project
        create_result = await client.call_tool("create_code_artifact", {
            "title": "Linked Artifact",
            "description": "Linked to project",
            "code": "# Has project",
            "language": "python",
            "tags": []
        })
        artifact_id = create_result.data.id

        # Link to project via update
        await client.call_tool("update_code_artifact", {
            "artifact_id": artifact_id,
            "project_id": project_id
        })

        # List artifacts filtered by project
        list_result = await client.call_tool("list_code_artifacts", {
            "project_id": project_id
        })

        artifacts = list_result.data["code_artifacts"]
        assert len(artifacts) == 1
        assert artifacts[0]["title"] == "Linked Artifact"
        assert artifacts[0]["project_id"] == project_id


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_code_artifact_e2e(docker_services, mcp_server_url):
    """Test updating a code artifact (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create artifact
        create_result = await client.call_tool("create_code_artifact", {
            "title": "Original Title",
            "description": "Original description",
            "code": "# Original code",
            "language": "python",
            "tags": ["original"]
        })

        artifact_id = create_result.data.id

        # Update only title and tags
        update_result = await client.call_tool("update_code_artifact", {
            "artifact_id": artifact_id,
            "title": "Updated Title",
            "tags": ["updated", "modified"]
        })

        assert update_result.data.title == "Updated Title"
        assert update_result.data.description == "Original description"  # Unchanged
        assert update_result.data.code == "# Original code"  # Unchanged
        assert update_result.data.tags == ["updated", "modified"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_code_artifact_e2e(docker_services, mcp_server_url):
    """Test deleting a code artifact"""
    async with Client(mcp_server_url) as client:
        # Create artifact
        create_result = await client.call_tool("create_code_artifact", {
            "title": "To Delete",
            "description": "Will be deleted",
            "code": "# Delete me",
            "language": "python",
            "tags": []
        })

        artifact_id = create_result.data.id

        # Delete artifact
        delete_result = await client.call_tool("delete_code_artifact", {
            "artifact_id": artifact_id
        })

        assert delete_result.data is not None
        assert delete_result.data["deleted_id"] == artifact_id

        # Verify artifact is gone
        try:
            await client.call_tool("get_code_artifact", {
                "artifact_id": artifact_id
            })
            assert False, "Expected error for deleted artifact"
        except Exception as e:
            assert "not found" in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_code_artifact_not_found_e2e(docker_services, mcp_server_url):
    """Test error handling for non-existent artifact"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("get_code_artifact", {
                "artifact_id": 999999
            })
            assert False, "Expected error for non-existent artifact"
        except Exception as e:
            assert "not found" in str(e).lower()
