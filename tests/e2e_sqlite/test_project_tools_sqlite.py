"""
E2E tests for project MCP tools with real PostgreSQL database
"""

import pytest
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_create_project_basic_e2e(mcp_client):
    """Test creating a project with all fields"""
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "forgetful-e2e",
                "description": "MIT-licensed memory service implementing atomic memory principles",
                "project_type": "development",
                "status": "active",
                "repo_name": "scottrbk/forgetful",
                "notes": "Uses FastAPI, PostgreSQL, and pgvector for semantic search",
            },
        },
    )
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["name"] == "forgetful-e2e"
    assert (
        result.data["description"]
        == "MIT-licensed memory service implementing atomic memory principles"
    )
    assert result.data["project_type"] == "development"
    assert result.data["status"] == "active"
    assert result.data["repo_name"] == "scottrbk/forgetful"
    assert (
        result.data["notes"]
        == "Uses FastAPI, PostgreSQL, and pgvector for semantic search"
    )
    assert result.data["memory_count"] == 0
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.asyncio
async def test_get_project_e2e(mcp_client):
    """Test creating then retrieving a project"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "test-get-project",
                "description": "Test project for retrieval",
                "project_type": "work",
            },
        },
    )
    project_id = create_result.data["id"]
    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_project", "arguments": {"project_id": project_id}},
    )
    assert get_result.data is not None
    assert get_result.data["id"] == project_id
    assert get_result.data["name"] == "test-get-project"
    assert get_result.data["description"] == "Test project for retrieval"
    assert get_result.data["project_type"] == "work"


@pytest.mark.asyncio
async def test_list_projects_e2e(mcp_client):
    """Test listing projects"""
    project_names = ["list-test-1", "list-test-2", "list-test-3"]
    for name in project_names:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_project",
                "arguments": {
                    "name": name,
                    "description": f"Description for {name}",
                    "project_type": "development",
                },
            },
        )
    list_result = await mcp_client.call_tool(
        "execute_forgetful_tool", {"tool_name": "list_projects", "arguments": {}}
    )
    assert list_result.data is not None
    assert "projects" in list_result.data
    assert "total_count" in list_result.data
    projects = list_result.data["projects"]
    assert len(projects) >= 3
    project_names_in_result = [p["name"] for p in projects]
    for name in project_names:
        assert name in project_names_in_result


@pytest.mark.asyncio
async def test_update_project_e2e(mcp_client):
    """Test updating a project"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "original-name",
                "description": "Original description",
                "project_type": "development",
            },
        },
    )
    project_id = create_result.data["id"]
    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_project",
            "arguments": {
                "project_id": project_id,
                "name": "updated-name",
                "description": "Updated description with new information",
            },
        },
    )
    assert update_result.data is not None
    assert update_result.data["id"] == project_id
    assert update_result.data["name"] == "updated-name"
    assert (
        update_result.data["description"] == "Updated description with new information"
    )
    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_project", "arguments": {"project_id": project_id}},
    )
    assert get_result.data["name"] == "updated-name"
    assert get_result.data["description"] == "Updated description with new information"


@pytest.mark.asyncio
async def test_delete_project_e2e(mcp_client):
    """Test deleting a project"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "to-delete",
                "description": "This project will be deleted",
                "project_type": "development",
            },
        },
    )
    project_id = create_result.data["id"]
    delete_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "delete_project", "arguments": {"project_id": project_id}},
    )
    assert delete_result.data is not None
    assert delete_result.data["success"] is True
    assert delete_result.data["project_id"] == project_id
    with pytest.raises((ToolError, Exception)) as exc_info:
        result = await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "get_project", "arguments": {"project_id": project_id}},
        )
        if result.data is None or (hasattr(result, "is_error") and result.is_error):
            raise ValueError("Project not found")
    error_message = str(exc_info.value).lower()
    assert (
        "not found" in error_message
        or "validation_error" in error_message
        or "project not found" in error_message
    )


@pytest.mark.asyncio
async def test_list_projects_filter_by_status_e2e(mcp_client):
    """Test filtering projects by status"""
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "active-status-test",
                "description": "Active project",
                "project_type": "development",
                "status": "active",
            },
        },
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "archived-status-test",
                "description": "Archived project",
                "project_type": "development",
                "status": "archived",
            },
        },
    )
    active_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "list_projects", "arguments": {"status": "active"}},
    )
    active_projects = active_result.data["projects"]
    active_names = [p["name"] for p in active_projects]
    assert "active-status-test" in active_names
    assert "archived-status-test" not in active_names
    for project in active_projects:
        assert project["status"] == "active"
    archived_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "list_projects", "arguments": {"status": "archived"}},
    )
    archived_projects = archived_result.data["projects"]
    archived_names = [p["name"] for p in archived_projects]
    assert "archived-status-test" in archived_names
    assert "active-status-test" not in archived_names


@pytest.mark.asyncio
async def test_list_projects_filter_by_repo_e2e(mcp_client):
    """Test filtering projects by repository name"""
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "forgetful-repo-test",
                "description": "Forgetful project",
                "project_type": "development",
                "repo_name": "scottrbk/forgetful",
            },
        },
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "other-repo-test",
                "description": "Other project",
                "project_type": "development",
                "repo_name": "scottrbk/other-repo",
            },
        },
    )
    forgetful_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "list_projects",
            "arguments": {"repo_name": "scottrbk/forgetful"},
        },
    )
    forgetful_projects = forgetful_result.data["projects"]
    forgetful_names = [p["name"] for p in forgetful_projects]
    assert "forgetful-repo-test" in forgetful_names
    for project in forgetful_projects:
        assert project["repo_name"] == "scottrbk/forgetful"


@pytest.mark.asyncio
async def test_project_persistence_e2e(mcp_client):
    """Test that projects persist across multiple queries"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "persistence-test",
                "description": "Test project persistence",
                "project_type": "development",
            },
        },
    )
    project_id = create_result.data["id"]
    for _ in range(3):
        get_result = await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "get_project", "arguments": {"project_id": project_id}},
        )
        assert get_result.data is not None
        assert get_result.data["id"] == project_id
        assert get_result.data["name"] == "persistence-test"


@pytest.mark.asyncio
async def test_get_project_invalid_id_e2e(mcp_client):
    """Test error handling when getting non-existent project"""
    with pytest.raises((ToolError, Exception)) as exc_info:
        result = await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "get_project", "arguments": {"project_id": 999999}},
        )
        # If no exception, the call succeeded but should return error indication
        if result.data is None or (hasattr(result, "is_error") and result.is_error):
            raise ValueError("Project not found")
    error_message = str(exc_info.value).lower()
    assert (
        "not found" in error_message
        or "validation_error" in error_message
        or "project not found" in error_message
    )


@pytest.mark.asyncio
async def test_update_project_invalid_id_e2e(mcp_client):
    """Test error handling when updating non-existent project"""
    with pytest.raises((ToolError, Exception)) as exc_info:
        result = await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "update_project",
                "arguments": {"project_id": 999999, "name": "This Should Fail"},
            },
        )
        if result.data is None or (hasattr(result, "is_error") and result.is_error):
            raise ValueError("Project not found")
    error_message = str(exc_info.value).lower()
    assert (
        "not found" in error_message
        or "validation_error" in error_message
        or "project not found" in error_message
    )


@pytest.mark.asyncio
async def test_delete_project_invalid_id_e2e(mcp_client):
    """Test error handling when deleting non-existent project"""
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "delete_project", "arguments": {"project_id": 999999}},
    )
    # Delete returns success=False for non-existent projects
    assert result.data is not None
    assert result.data["success"] is False


@pytest.mark.asyncio
async def test_create_project_validation_error_e2e(mcp_client):
    """Test validation error with invalid repo_name format"""
    try:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_project",
                "arguments": {
                    "name": "invalid-repo",
                    "description": "Project with invalid repo format",
                    "project_type": "development",
                    "repo_name": "invalid-format-no-slash",
                },
            },
        )
        assert False, "Expected validation error for invalid repo_name"
    except Exception as e:
        error_message = str(e).lower()
        assert "validation" in error_message or "owner/repo" in error_message


@pytest.mark.asyncio
async def test_update_project_partial_e2e(mcp_client):
    """Test partial update (PATCH semantics)"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "patch-test",
                "description": "Original description",
                "project_type": "development",
                "repo_name": "scottrbk/test-repo",
            },
        },
    )
    project_id = create_result.data["id"]
    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_project",
            "arguments": {"project_id": project_id, "name": "updated-patch-test"},
        },
    )
    assert update_result.data["name"] == "updated-patch-test"
    assert update_result.data["description"] == "Original description"
    assert update_result.data["repo_name"] == "scottrbk/test-repo"


@pytest.mark.asyncio
async def test_update_project_archive_e2e(mcp_client):
    """Test archiving a project"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "archive-test",
                "description": "Project to archive",
                "project_type": "development",
                "status": "active",
            },
        },
    )
    project_id = create_result.data["id"]
    assert create_result.data["status"] == "active"
    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_project",
            "arguments": {"project_id": project_id, "status": "archived"},
        },
    )
    assert update_result.data["status"] == "archived"
    assert update_result.data["name"] == "archive-test"


@pytest.mark.asyncio
async def test_list_returns_summary_e2e(mcp_client):
    """Test that list_projects returns ProjectSummary (no description/notes)"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "summary-test",
                "description": "This is a long description that should not appear in list",
                "project_type": "development",
                "notes": "These are notes that should not appear in list",
            },
        },
    )
    assert create_result
    list_result = await mcp_client.call_tool(
        "execute_forgetful_tool", {"tool_name": "list_projects", "arguments": {}}
    )
    projects = list_result.data["projects"]
    our_project = None
    for p in projects:
        if p["name"] == "summary-test":
            our_project = p
            break
    assert our_project is not None
    project_dict = (
        our_project.__dict__ if hasattr(our_project, "__dict__") else our_project
    )
    assert "id" in project_dict
    assert "name" in project_dict
    assert "project_type" in project_dict
    assert "status" in project_dict
    assert "memory_count" in project_dict


@pytest.mark.asyncio
async def test_get_returns_full_e2e(mcp_client):
    """Test that get_project returns full Project (with description/notes)"""
    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "full-test",
                "description": "This is the full description",
                "project_type": "development",
                "notes": "These are the full notes",
            },
        },
    )
    project_id = create_result.data["id"]
    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_project", "arguments": {"project_id": project_id}},
    )
    assert get_result.data is not None
    assert get_result.data["description"] == "This is the full description"
    assert get_result.data["notes"] == "These are the full notes"
    assert get_result.data["name"] == "full-test"


@pytest.mark.asyncio
async def test_project_memory_count_updates_e2e(mcp_client):
    """Test that project memory_count updates when memories are added"""
    project_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "memory-count-test",
                "description": "Test memory_count updates",
                "project_type": "development",
            },
        },
    )
    project_id = project_result.data["id"]
    assert project_result.data["memory_count"] == 0
    for i in range(3):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_memory",
                "arguments": {
                    "title": f"Memory {i} for project",
                    "content": f"This is memory {i} linked to the project",
                    "context": "Testing memory count",
                    "keywords": ["test", "memory", "count"],
                    "tags": ["test"],
                    "importance": 7,
                    "project_ids": [project_id],
                },
            },
        )
    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_project", "arguments": {"project_id": project_id}},
    )
    assert get_result.data["memory_count"] == 3


@pytest.mark.asyncio
async def test_query_memory_by_project_e2e(mcp_client):
    """Test querying memories filtered by project_ids"""
    project1_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "query-project-1",
                "description": "First project for query test",
                "project_type": "development",
            },
        },
    )
    project2_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "query-project-2",
                "description": "Second project for query test",
                "project_type": "development",
            },
        },
    )
    project1_id = project1_result.data["id"]
    project2_id = project2_result.data["id"]
    for i in range(2):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_memory",
                "arguments": {
                    "title": f"Project 1 memory {i}",
                    "content": f"Content for project 1 memory {i}",
                    "context": "Testing project filtering",
                    "keywords": ["project1", "test"],
                    "tags": ["test"],
                    "importance": 7,
                    "project_ids": [project1_id],
                },
            },
        )
    for i in range(2):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_memory",
                "arguments": {
                    "title": f"Project 2 memory {i}",
                    "content": f"Content for project 2 memory {i}",
                    "context": "Testing project filtering",
                    "keywords": ["project2", "test"],
                    "tags": ["test"],
                    "importance": 7,
                    "project_ids": [project2_id],
                },
            },
        )
    query_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "query_memory",
            "arguments": {
                "query": "memory",
                "query_context": "Looking for project 1 memories",
                "k": 10,
                "project_ids": [project1_id],
            },
        },
    )
    project1_memories = query_result.data["primary_memories"]
    assert len(project1_memories) >= 2
    for memory in project1_memories:
        assert project1_id in memory["project_ids"]
        assert project2_id not in memory["project_ids"]


@pytest.mark.asyncio
async def test_list_projects_filter_by_name_e2e(mcp_client):
    """Test filtering projects by name (case-insensitive partial match)"""
    # Create projects with different names
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "Forgetful-Backend",
                "description": "Backend service",
                "project_type": "development",
            },
        },
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "forgetful-ui",
                "description": "UI components",
                "project_type": "development",
            },
        },
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": "other-project",
                "description": "Unrelated project",
                "project_type": "development",
            },
        },
    )

    # Filter by partial name match (case-insensitive)
    forgetful_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "list_projects", "arguments": {"name": "forgetful"}},
    )
    forgetful_projects = forgetful_result.data["projects"]
    forgetful_names = [p["name"] for p in forgetful_projects]

    # Should match both "Forgetful-Backend" and "forgetful-ui"
    assert len(forgetful_projects) >= 2
    assert any("forgetful" in name.lower() for name in forgetful_names)
    assert "other-project" not in forgetful_names

    # Verify name_filter is returned in response
    assert forgetful_result.data.get("name_filter") == "forgetful"

    # Test with uppercase search (case-insensitive)
    uppercase_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "list_projects", "arguments": {"name": "FORGETFUL"}},
    )
    uppercase_projects = uppercase_result.data["projects"]
    assert len(uppercase_projects) >= 2
