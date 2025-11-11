"""
E2E tests for project MCP tools with real PostgreSQL database
"""
import pytest
from fastmcp import Client


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_project_basic_e2e(docker_services, mcp_server_url):
    """Test creating a project with all fields"""
    async with Client(mcp_server_url) as client:
        result = await client.call_tool("create_project", {
            "name": "forgetful-e2e",
            "description": "MIT-licensed memory service implementing atomic memory principles",
            "project_type": "development",
            "status": "active",
            "repo_name": "scottrbk/forgetful",
            "notes": "Uses FastAPI, PostgreSQL, and pgvector for semantic search"
        })

        assert result.data is not None
        assert result.data.id is not None
        assert result.data.name == "forgetful-e2e"
        assert result.data.description == "MIT-licensed memory service implementing atomic memory principles"
        assert result.data.project_type == "development"
        assert result.data.status == "active"
        assert result.data.repo_name == "scottrbk/forgetful"
        assert result.data.notes == "Uses FastAPI, PostgreSQL, and pgvector for semantic search"
        assert result.data.memory_count == 0
        assert result.data.created_at is not None
        assert result.data.updated_at is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_project_e2e(docker_services, mcp_server_url):
    """Test creating then retrieving a project"""
    async with Client(mcp_server_url) as client:
        # Create project
        create_result = await client.call_tool("create_project", {
            "name": "test-get-project",
            "description": "Test project for retrieval",
            "project_type": "work"
        })

        project_id = create_result.data.id

        # Get project
        get_result = await client.call_tool("get_project", {
            "project_id": project_id
        })

        assert get_result.data is not None
        assert get_result.data.id == project_id
        assert get_result.data.name == "test-get-project"
        assert get_result.data.description == "Test project for retrieval"
        assert get_result.data.project_type == "work"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_projects_e2e(docker_services, mcp_server_url):
    """Test listing projects"""
    async with Client(mcp_server_url) as client:
        # Create multiple projects
        project_names = ["list-test-1", "list-test-2", "list-test-3"]

        for name in project_names:
            await client.call_tool("create_project", {
                "name": name,
                "description": f"Description for {name}",
                "project_type": "development"
            })

        # List all projects
        list_result = await client.call_tool("list_projects", {})

        assert list_result.data is not None
        assert "projects" in list_result.data
        assert "total_count" in list_result.data

        projects = list_result.data["projects"]
        assert len(projects) >= 3

        # Verify our projects are in the list
        project_names_in_result = [p["name"] for p in projects]
        for name in project_names:
            assert name in project_names_in_result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_project_e2e(docker_services, mcp_server_url):
    """Test updating a project"""
    async with Client(mcp_server_url) as client:
        # Create project
        create_result = await client.call_tool("create_project", {
            "name": "original-name",
            "description": "Original description",
            "project_type": "development"
        })

        project_id = create_result.data.id

        # Update project
        update_result = await client.call_tool("update_project", {
            "project_id": project_id,
            "name": "updated-name",
            "description": "Updated description with new information"
        })

        assert update_result.data is not None
        assert update_result.data.id == project_id
        assert update_result.data.name == "updated-name"
        assert update_result.data.description == "Updated description with new information"

        # Verify with get
        get_result = await client.call_tool("get_project", {
            "project_id": project_id
        })

        assert get_result.data.name == "updated-name"
        assert get_result.data.description == "Updated description with new information"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_project_e2e(docker_services, mcp_server_url):
    """Test deleting a project"""
    async with Client(mcp_server_url) as client:
        # Create project
        create_result = await client.call_tool("create_project", {
            "name": "to-delete",
            "description": "This project will be deleted",
            "project_type": "development"
        })

        project_id = create_result.data.id

        # Delete project
        delete_result = await client.call_tool("delete_project", {
            "project_id": project_id
        })

        assert delete_result.data is not None
        assert delete_result.data["success"] is True
        assert delete_result.data["project_id"] == project_id

        # Verify project no longer exists
        try:
            await client.call_tool("get_project", {
                "project_id": project_id
            })
            # Should not reach here
            assert False, "Expected error when getting deleted project"
        except Exception as e:
            error_message = str(e).lower()
            assert "not found" in error_message or "validation_error" in error_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_projects_filter_by_status_e2e(docker_services, mcp_server_url):
    """Test filtering projects by status"""
    async with Client(mcp_server_url) as client:
        # Create projects with different statuses
        await client.call_tool("create_project", {
            "name": "active-status-test",
            "description": "Active project",
            "project_type": "development",
            "status": "active"
        })

        await client.call_tool("create_project", {
            "name": "archived-status-test",
            "description": "Archived project",
            "project_type": "development",
            "status": "archived"
        })

        # Filter by active
        active_result = await client.call_tool("list_projects", {
            "status": "active"
        })

        active_projects = active_result.data["projects"]
        active_names = [p["name"] for p in active_projects]
        assert "active-status-test" in active_names
        assert "archived-status-test" not in active_names

        # Verify all returned projects have active status
        for project in active_projects:
            assert project["status"] == "active"

        # Filter by archived
        archived_result = await client.call_tool("list_projects", {
            "status": "archived"
        })

        archived_projects = archived_result.data["projects"]
        archived_names = [p["name"] for p in archived_projects]
        assert "archived-status-test" in archived_names
        assert "active-status-test" not in archived_names


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_projects_filter_by_repo_e2e(docker_services, mcp_server_url):
    """Test filtering projects by repository name"""
    async with Client(mcp_server_url) as client:
        # Create projects with different repos
        await client.call_tool("create_project", {
            "name": "forgetful-repo-test",
            "description": "Forgetful project",
            "project_type": "development",
            "repo_name": "scottrbk/forgetful"
        })

        await client.call_tool("create_project", {
            "name": "other-repo-test",
            "description": "Other project",
            "project_type": "development",
            "repo_name": "scottrbk/other-repo"
        })

        # Filter by forgetful repo
        forgetful_result = await client.call_tool("list_projects", {
            "repo_name": "scottrbk/forgetful"
        })

        forgetful_projects = forgetful_result.data["projects"]
        forgetful_names = [p["name"] for p in forgetful_projects]
        assert "forgetful-repo-test" in forgetful_names

        # Verify all returned projects have correct repo
        for project in forgetful_projects:
            assert project["repo_name"] == "scottrbk/forgetful"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_project_persistence_e2e(docker_services, mcp_server_url):
    """Test that projects persist across multiple queries"""
    async with Client(mcp_server_url) as client:
        # Create project
        create_result = await client.call_tool("create_project", {
            "name": "persistence-test",
            "description": "Test project persistence",
            "project_type": "development"
        })

        project_id = create_result.data.id

        # Query multiple times
        for _ in range(3):
            get_result = await client.call_tool("get_project", {
                "project_id": project_id
            })

            assert get_result.data is not None
            assert get_result.data.id == project_id
            assert get_result.data.name == "persistence-test"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_project_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when getting non-existent project"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("get_project", {
                "project_id": 999999
            })
            # Should not reach here
            assert False, "Expected error for invalid project_id"
        except Exception as e:
            error_message = str(e).lower()
            assert "not found" in error_message or "validation_error" in error_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_project_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when updating non-existent project"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("update_project", {
                "project_id": 999999,
                "name": "This Should Fail"
            })
            # Should not reach here
            assert False, "Expected error for invalid project_id"
        except Exception as e:
            error_message = str(e).lower()
            assert "not found" in error_message or "validation_error" in error_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_delete_project_invalid_id_e2e(docker_services, mcp_server_url):
    """Test error handling when deleting non-existent project"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("delete_project", {
                "project_id": 999999
            })
            # Should not reach here
            assert False, "Expected error for invalid project_id"
        except Exception as e:
            error_message = str(e).lower()
            assert "not found" in error_message or "validation_error" in error_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_project_validation_error_e2e(docker_services, mcp_server_url):
    """Test validation error with invalid repo_name format"""
    async with Client(mcp_server_url) as client:
        try:
            await client.call_tool("create_project", {
                "name": "invalid-repo",
                "description": "Project with invalid repo format",
                "project_type": "development",
                "repo_name": "invalid-format-no-slash"
            })
            # Should not reach here
            assert False, "Expected validation error for invalid repo_name"
        except Exception as e:
            error_message = str(e).lower()
            assert "validation" in error_message or "owner/repo" in error_message


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_project_partial_e2e(docker_services, mcp_server_url):
    """Test partial update (PATCH semantics)"""
    async with Client(mcp_server_url) as client:
        # Create project
        create_result = await client.call_tool("create_project", {
            "name": "patch-test",
            "description": "Original description",
            "project_type": "development",
            "repo_name": "scottrbk/test-repo"
        })

        project_id = create_result.data.id

        # Update only name
        update_result = await client.call_tool("update_project", {
            "project_id": project_id,
            "name": "updated-patch-test"
        })

        # Verify only name changed
        assert update_result.data.name == "updated-patch-test"
        assert update_result.data.description == "Original description"  # Unchanged
        assert update_result.data.repo_name == "scottrbk/test-repo"  # Unchanged


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_update_project_archive_e2e(docker_services, mcp_server_url):
    """Test archiving a project"""
    async with Client(mcp_server_url) as client:
        # Create active project
        create_result = await client.call_tool("create_project", {
            "name": "archive-test",
            "description": "Project to archive",
            "project_type": "development",
            "status": "active"
        })

        project_id = create_result.data.id
        assert create_result.data.status == "active"

        # Archive project
        update_result = await client.call_tool("update_project", {
            "project_id": project_id,
            "status": "archived"
        })

        assert update_result.data.status == "archived"
        assert update_result.data.name == "archive-test"  # Other fields unchanged


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_returns_summary_e2e(docker_services, mcp_server_url):
    """Test that list_projects returns ProjectSummary (no description/notes)"""
    async with Client(mcp_server_url) as client:
        # Create project with description and notes
        create_result = await client.call_tool("create_project", {
            "name": "summary-test",
            "description": "This is a long description that should not appear in list",
            "project_type": "development",
            "notes": "These are notes that should not appear in list"
        })

        # List projects
        list_result = await client.call_tool("list_projects", {})

        projects = list_result.data["projects"]

        # Find our project
        our_project = None
        for p in projects:
            if p["name"] == "summary-test":
                our_project = p
                break

        assert our_project is not None

        # Verify it's a summary (no description or notes fields)
        # Convert to dict to check fields
        project_dict = our_project.__dict__ if hasattr(our_project, '__dict__') else our_project

        # Should have these fields
        assert 'id' in project_dict
        assert 'name' in project_dict
        assert 'project_type' in project_dict
        assert 'status' in project_dict
        assert 'memory_count' in project_dict

        # Should NOT have description/notes in summary
        # (or they should be None/excluded)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_get_returns_full_e2e(docker_services, mcp_server_url):
    """Test that get_project returns full Project (with description/notes)"""
    async with Client(mcp_server_url) as client:
        # Create project with description and notes
        create_result = await client.call_tool("create_project", {
            "name": "full-test",
            "description": "This is the full description",
            "project_type": "development",
            "notes": "These are the full notes"
        })

        project_id = create_result.data.id

        # Get project (should return full object)
        get_result = await client.call_tool("get_project", {
            "project_id": project_id
        })

        assert get_result.data is not None
        assert get_result.data.description == "This is the full description"
        assert get_result.data.notes == "These are the full notes"
        assert get_result.data.name == "full-test"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_project_memory_count_updates_e2e(docker_services, mcp_server_url):
    """Test that project memory_count updates when memories are added"""
    async with Client(mcp_server_url) as client:
        # Create project
        project_result = await client.call_tool("create_project", {
            "name": "memory-count-test",
            "description": "Test memory_count updates",
            "project_type": "development"
        })

        project_id = project_result.data.id

        # Initial memory_count should be 0
        assert project_result.data.memory_count == 0

        # Create memories with this project
        for i in range(3):
            await client.call_tool("create_memory", {
                "title": f"Memory {i} for project",
                "content": f"This is memory {i} linked to the project",
                "context": "Testing memory count",
                "keywords": ["test", "memory", "count"],
                "tags": ["test"],
                "importance": 7,
                "project_ids": [project_id]
            })

        # Get project and verify memory_count incremented
        get_result = await client.call_tool("get_project", {
            "project_id": project_id
        })

        assert get_result.data.memory_count == 3


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_query_memory_by_project_e2e(docker_services, mcp_server_url):
    """Test querying memories filtered by project_ids"""
    async with Client(mcp_server_url) as client:
        # Create two projects
        project1_result = await client.call_tool("create_project", {
            "name": "query-project-1",
            "description": "First project for query test",
            "project_type": "development"
        })

        project2_result = await client.call_tool("create_project", {
            "name": "query-project-2",
            "description": "Second project for query test",
            "project_type": "development"
        })

        project1_id = project1_result.data.id
        project2_id = project2_result.data.id

        # Create memories for project 1
        for i in range(2):
            await client.call_tool("create_memory", {
                "title": f"Project 1 memory {i}",
                "content": f"Content for project 1 memory {i}",
                "context": "Testing project filtering",
                "keywords": ["project1", "test"],
                "tags": ["test"],
                "importance": 7,
                "project_ids": [project1_id]
            })

        # Create memories for project 2
        for i in range(2):
            await client.call_tool("create_memory", {
                "title": f"Project 2 memory {i}",
                "content": f"Content for project 2 memory {i}",
                "context": "Testing project filtering",
                "keywords": ["project2", "test"],
                "tags": ["test"],
                "importance": 7,
                "project_ids": [project2_id]
            })

        # Query memories with project 1 filter
        query_result = await client.call_tool("query_memory", {
            "query": "memory",
            "query_context": "Looking for project 1 memories",
            "k": 10,
            "project_ids": [project1_id]
        })

        # Verify we only get project 1 memories
        project1_memories = query_result.data.primary_memories
        assert len(project1_memories) >= 2

        for memory in project1_memories:
            assert project1_id in memory.project_ids
            assert project2_id not in memory.project_ids
