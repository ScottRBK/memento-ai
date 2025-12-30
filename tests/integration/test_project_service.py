"""
Integration tests for ProjectService with in-memory stubs
"""

from uuid import uuid4

import pytest

from app.models.project_models import (
    ProjectCreate,
    ProjectStatus,
    ProjectType,
    ProjectUpdate,
)


@pytest.mark.asyncio
async def test_create_project_basic(test_project_service):
    """Test creating a project with all fields"""
    user_id = uuid4()

    project_data = ProjectCreate(
        name="forgetful",
        description="MIT-licensed memory service implementing atomic memory principles",
        project_type=ProjectType.DEVELOPMENT,
        status=ProjectStatus.ACTIVE,
        repo_name="scottrbk/forgetful",
        notes="Uses FastAPI, PostgreSQL, and pgvector for semantic search",
    )

    project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    assert project is not None
    assert project.id is not None
    assert project.name == "forgetful"
    assert (
        project.description
        == "MIT-licensed memory service implementing atomic memory principles"
    )
    assert project.project_type == ProjectType.DEVELOPMENT
    assert project.status == ProjectStatus.ACTIVE
    assert project.repo_name == "scottrbk/forgetful"
    assert project.notes == "Uses FastAPI, PostgreSQL, and pgvector for semantic search"
    assert project.memory_count == 0
    assert project.created_at is not None
    assert project.updated_at is not None


@pytest.mark.asyncio
async def test_create_project_minimal(test_project_service):
    """Test creating a project with only required fields"""
    user_id = uuid4()

    project_data = ProjectCreate(
        name="minimal-project",
        description="A minimal project for testing",
        project_type=ProjectType.PERSONAL,
    )

    project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    assert project is not None
    assert project.id is not None
    assert project.name == "minimal-project"
    assert project.description == "A minimal project for testing"
    assert project.project_type == ProjectType.PERSONAL
    assert project.status == ProjectStatus.ACTIVE  # Default status
    assert project.repo_name is None
    assert project.notes is None
    assert project.memory_count == 0


@pytest.mark.asyncio
async def test_get_project(test_project_service):
    """Test retrieving a project by ID"""
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="test-project",
        description="Test project for retrieval",
        project_type=ProjectType.WORK,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    # Retrieve project
    retrieved_project = await test_project_service.get_project(
        user_id=user_id, project_id=created_project.id
    )

    assert retrieved_project is not None
    assert retrieved_project.id == created_project.id
    assert retrieved_project.name == "test-project"
    assert retrieved_project.description == "Test project for retrieval"


@pytest.mark.asyncio
async def test_get_project_not_found(test_project_service):
    """Test retrieving a non-existent project"""
    user_id = uuid4()

    project = await test_project_service.get_project(user_id=user_id, project_id=99999)

    assert project is None


@pytest.mark.asyncio
async def test_list_projects_empty(test_project_service):
    """Test listing projects when none exist"""
    user_id = uuid4()

    projects = await test_project_service.list_projects(user_id=user_id)

    assert isinstance(projects, list)
    assert len(projects) == 0


@pytest.mark.asyncio
async def test_list_projects_multiple(test_project_service):
    """Test listing multiple projects"""
    user_id = uuid4()

    # Create multiple projects
    for i in range(3):
        project_data = ProjectCreate(
            name=f"project-{i}",
            description=f"Test project {i}",
            project_type=ProjectType.DEVELOPMENT,
        )
        await test_project_service.create_project(
            user_id=user_id, project_data=project_data
        )

    # List all projects
    projects = await test_project_service.list_projects(user_id=user_id)

    assert len(projects) == 3
    # Should be sorted by created_at desc (newest first)
    assert projects[0].name == "project-2"
    assert projects[1].name == "project-1"
    assert projects[2].name == "project-0"

    # Verify they're ProjectSummary objects (not full Project)
    for project in projects:
        assert hasattr(project, "id")
        assert hasattr(project, "name")
        assert hasattr(project, "project_type")
        assert hasattr(project, "status")
        assert hasattr(project, "memory_count")


@pytest.mark.asyncio
async def test_list_projects_filter_by_status(test_project_service):
    """Test filtering projects by status"""
    user_id = uuid4()

    # Create projects with different statuses
    active_project = ProjectCreate(
        name="active-project",
        description="Active project",
        project_type=ProjectType.DEVELOPMENT,
        status=ProjectStatus.ACTIVE,
    )

    archived_project = ProjectCreate(
        name="archived-project",
        description="Archived project",
        project_type=ProjectType.DEVELOPMENT,
        status=ProjectStatus.ARCHIVED,
    )

    completed_project = ProjectCreate(
        name="completed-project",
        description="Completed project",
        project_type=ProjectType.DEVELOPMENT,
        status=ProjectStatus.COMPLETED,
    )

    await test_project_service.create_project(user_id, active_project)
    await test_project_service.create_project(user_id, archived_project)
    await test_project_service.create_project(user_id, completed_project)

    # Filter by active
    active_projects = await test_project_service.list_projects(
        user_id=user_id, status=ProjectStatus.ACTIVE
    )
    assert len(active_projects) == 1
    assert active_projects[0].name == "active-project"
    assert active_projects[0].status == ProjectStatus.ACTIVE

    # Filter by archived
    archived_projects = await test_project_service.list_projects(
        user_id=user_id, status=ProjectStatus.ARCHIVED
    )
    assert len(archived_projects) == 1
    assert archived_projects[0].name == "archived-project"
    assert archived_projects[0].status == ProjectStatus.ARCHIVED

    # Filter by completed
    completed_projects = await test_project_service.list_projects(
        user_id=user_id, status=ProjectStatus.COMPLETED
    )
    assert len(completed_projects) == 1
    assert completed_projects[0].name == "completed-project"
    assert completed_projects[0].status == ProjectStatus.COMPLETED


@pytest.mark.asyncio
async def test_list_projects_filter_by_repo(test_project_service):
    """Test filtering projects by repository name"""
    user_id = uuid4()

    # Create projects with different repos
    project1 = ProjectCreate(
        name="project1",
        description="Project 1",
        project_type=ProjectType.DEVELOPMENT,
        repo_name="scottrbk/forgetful",
    )

    project2 = ProjectCreate(
        name="project2",
        description="Project 2",
        project_type=ProjectType.DEVELOPMENT,
        repo_name="scottrbk/other-repo",
    )

    project3 = ProjectCreate(
        name="project3",
        description="Project 3 without repo",
        project_type=ProjectType.DEVELOPMENT,
    )

    await test_project_service.create_project(user_id, project1)
    await test_project_service.create_project(user_id, project2)
    await test_project_service.create_project(user_id, project3)

    # Filter by specific repo
    forgetful_projects = await test_project_service.list_projects(
        user_id=user_id, repo_name="scottrbk/forgetful"
    )
    assert len(forgetful_projects) == 1
    assert forgetful_projects[0].name == "project1"
    assert forgetful_projects[0].repo_name == "scottrbk/forgetful"

    # Filter by different repo
    other_projects = await test_project_service.list_projects(
        user_id=user_id, repo_name="scottrbk/other-repo"
    )
    assert len(other_projects) == 1
    assert other_projects[0].name == "project2"


@pytest.mark.asyncio
async def test_list_projects_combined_filters(test_project_service):
    """Test filtering projects by both status and repo_name"""
    user_id = uuid4()

    # Create projects with various combinations
    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="active-forgetful",
            description="Active forgetful project",
            project_type=ProjectType.DEVELOPMENT,
            status=ProjectStatus.ACTIVE,
            repo_name="scottrbk/forgetful",
        ),
    )

    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="archived-forgetful",
            description="Archived forgetful project",
            project_type=ProjectType.DEVELOPMENT,
            status=ProjectStatus.ARCHIVED,
            repo_name="scottrbk/forgetful",
        ),
    )

    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="active-other",
            description="Active other project",
            project_type=ProjectType.DEVELOPMENT,
            status=ProjectStatus.ACTIVE,
            repo_name="scottrbk/other-repo",
        ),
    )

    # Filter by active + forgetful
    filtered_projects = await test_project_service.list_projects(
        user_id=user_id, status=ProjectStatus.ACTIVE, repo_name="scottrbk/forgetful"
    )

    assert len(filtered_projects) == 1
    assert filtered_projects[0].name == "active-forgetful"
    assert filtered_projects[0].status == ProjectStatus.ACTIVE
    assert filtered_projects[0].repo_name == "scottrbk/forgetful"


@pytest.mark.asyncio
async def test_update_project_single_field(test_project_service):
    """Test updating a single field of a project"""
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="original-name",
        description="Original description",
        project_type=ProjectType.DEVELOPMENT,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    # Update only name
    update_data = ProjectUpdate(name="updated-name")

    updated_project = await test_project_service.update_project(
        user_id=user_id, project_id=created_project.id, project_data=update_data
    )

    assert updated_project is not None
    assert updated_project.id == created_project.id
    assert updated_project.name == "updated-name"
    # Other fields should remain unchanged
    assert updated_project.description == "Original description"
    assert updated_project.project_type == ProjectType.DEVELOPMENT
    assert (
        updated_project.updated_at >= created_project.updated_at
    )  # >= to handle in-memory timing


@pytest.mark.asyncio
async def test_update_project_multiple_fields(test_project_service):
    """Test updating multiple fields of a project"""
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="original-name",
        description="Original description",
        project_type=ProjectType.DEVELOPMENT,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    # Update name and description
    update_data = ProjectUpdate(
        name="updated-name", description="Updated description with new information"
    )

    updated_project = await test_project_service.update_project(
        user_id=user_id, project_id=created_project.id, project_data=update_data
    )

    assert updated_project is not None
    assert updated_project.name == "updated-name"
    assert updated_project.description == "Updated description with new information"
    assert updated_project.project_type == ProjectType.DEVELOPMENT  # Unchanged


@pytest.mark.asyncio
async def test_update_project_status_change(test_project_service):
    """Test archiving a project by changing status"""
    user_id = uuid4()

    # Create active project
    project_data = ProjectCreate(
        name="test-project",
        description="Test project",
        project_type=ProjectType.DEVELOPMENT,
        status=ProjectStatus.ACTIVE,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    assert created_project.status == ProjectStatus.ACTIVE

    # Archive project
    update_data = ProjectUpdate(status=ProjectStatus.ARCHIVED)

    updated_project = await test_project_service.update_project(
        user_id=user_id, project_id=created_project.id, project_data=update_data
    )

    assert updated_project.status == ProjectStatus.ARCHIVED
    assert updated_project.name == "test-project"  # Other fields unchanged


@pytest.mark.asyncio
async def test_update_project_no_changes(test_project_service):
    """Test updating a project with no actual changes"""
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="test-project",
        description="Test description",
        project_type=ProjectType.DEVELOPMENT,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    original_updated_at = created_project.updated_at

    # Update with same values
    update_data = ProjectUpdate(name="test-project", description="Test description")

    updated_project = await test_project_service.update_project(
        user_id=user_id, project_id=created_project.id, project_data=update_data
    )

    # Should return existing project without changes
    assert updated_project is not None
    assert updated_project.id == created_project.id
    assert updated_project.name == "test-project"
    assert updated_project.description == "Test description"
    # No actual changes, so updated_at should remain the same
    assert updated_project.updated_at == original_updated_at


@pytest.mark.asyncio
async def test_update_project_not_found(test_project_service):
    """Test updating a non-existent project"""
    user_id = uuid4()

    update_data = ProjectUpdate(name="updated-name")

    updated_project = await test_project_service.update_project(
        user_id=user_id, project_id=99999, project_data=update_data
    )

    assert updated_project is None


@pytest.mark.asyncio
async def test_delete_project(test_project_service):
    """Test deleting a project"""
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="to-delete",
        description="This project will be deleted",
        project_type=ProjectType.DEVELOPMENT,
    )

    created_project = await test_project_service.create_project(
        user_id=user_id, project_data=project_data
    )

    # Delete project
    success = await test_project_service.delete_project(
        user_id=user_id, project_id=created_project.id
    )

    assert success is True

    # Verify project no longer exists
    deleted_project = await test_project_service.get_project(
        user_id=user_id, project_id=created_project.id
    )

    assert deleted_project is None


@pytest.mark.asyncio
async def test_delete_project_not_found(test_project_service):
    """Test deleting a non-existent project"""
    user_id = uuid4()

    success = await test_project_service.delete_project(
        user_id=user_id, project_id=99999
    )

    assert success is False


@pytest.mark.asyncio
async def test_project_user_isolation(test_project_service):
    """Test that users can only see their own projects"""
    user1_id = uuid4()
    user2_id = uuid4()

    # User 1 creates a project
    project_data = ProjectCreate(
        name="user1-project",
        description="User 1's project",
        project_type=ProjectType.PERSONAL,
    )

    user1_project = await test_project_service.create_project(
        user_id=user1_id, project_data=project_data
    )

    # User 2 tries to get user 1's project
    retrieved_project = await test_project_service.get_project(
        user_id=user2_id, project_id=user1_project.id
    )

    assert retrieved_project is None

    # User 2 lists projects - should not see user 1's project
    user2_projects = await test_project_service.list_projects(user_id=user2_id)
    assert len(user2_projects) == 0

    # User 1 can see their own project
    user1_projects = await test_project_service.list_projects(user_id=user1_id)
    assert len(user1_projects) == 1
    assert user1_projects[0].name == "user1-project"


@pytest.mark.asyncio
async def test_list_projects_filter_by_name(test_project_service):
    """Test filtering projects by name (partial match)"""
    user_id = uuid4()

    # Create projects with different names
    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="forgetful-backend",
            description="Backend service",
            project_type=ProjectType.DEVELOPMENT,
        ),
    )

    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="forgetful-ui",
            description="UI components",
            project_type=ProjectType.DEVELOPMENT,
        ),
    )

    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="other-project",
            description="Unrelated project",
            project_type=ProjectType.DEVELOPMENT,
        ),
    )

    # Filter by partial name match
    forgetful_projects = await test_project_service.list_projects(
        user_id=user_id, name="forgetful"
    )
    assert len(forgetful_projects) == 2
    project_names = [p.name for p in forgetful_projects]
    assert "forgetful-backend" in project_names or "forgetful-ui" in project_names

    # Filter with different partial match
    backend_projects = await test_project_service.list_projects(
        user_id=user_id, name="backend"
    )
    assert len(backend_projects) == 1
    assert backend_projects[0].name == "forgetful-backend"

    # No match
    no_match = await test_project_service.list_projects(
        user_id=user_id, name="nonexistent"
    )
    assert len(no_match) == 0


@pytest.mark.asyncio
async def test_list_projects_filter_by_name_case_insensitive(test_project_service):
    """Test that name filtering is case-insensitive"""
    user_id = uuid4()

    # Create project with mixed case name
    await test_project_service.create_project(
        user_id,
        ProjectCreate(
            name="Forgetful-Project",
            description="Mixed case project name",
            project_type=ProjectType.DEVELOPMENT,
        ),
    )

    # Search with lowercase
    lowercase_match = await test_project_service.list_projects(
        user_id=user_id, name="forgetful"
    )
    assert len(lowercase_match) == 1
    assert lowercase_match[0].name == "Forgetful-Project"

    # Search with uppercase
    uppercase_match = await test_project_service.list_projects(
        user_id=user_id, name="FORGETFUL"
    )
    assert len(uppercase_match) == 1
    assert uppercase_match[0].name == "Forgetful-Project"

    # Search with mixed case
    mixedcase_match = await test_project_service.list_projects(
        user_id=user_id, name="FoRgEtFuL"
    )
    assert len(mixedcase_match) == 1
    assert mixedcase_match[0].name == "Forgetful-Project"
