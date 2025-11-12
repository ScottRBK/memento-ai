"""
Integration tests for CodeArtifactService with in-memory stubs
"""
import pytest
from uuid import uuid4

from app.models.code_artifact_models import CodeArtifactCreate, CodeArtifactUpdate
from app.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_code_artifact(test_code_artifact_service):
    user_id = uuid4()

    artifact_data = CodeArtifactCreate(
        title="JWT Middleware",
        description="FastAPI JWT validation",
        code="@app.middleware('http')\nasync def jwt_middleware(request, call_next):\n    return await call_next(request)",
        language="python",
        tags=["fastapi", "auth"]
    )

    artifact = await test_code_artifact_service.create_code_artifact(user_id, artifact_data)

    assert artifact.id is not None
    assert artifact.title == "JWT Middleware"
    assert artifact.language == "python"
    assert artifact.tags == ["fastapi", "auth"]


@pytest.mark.asyncio
async def test_get_code_artifact(test_code_artifact_service):
    user_id = uuid4()

    # Create
    artifact_data = CodeArtifactCreate(
        title="Test Artifact",
        description="Test",
        code="print('hello')",
        language="python",
        tags=[]
    )
    created = await test_code_artifact_service.create_code_artifact(user_id, artifact_data)

    # Get
    retrieved = await test_code_artifact_service.get_code_artifact(user_id, created.id)

    assert retrieved.id == created.id
    assert retrieved.title == "Test Artifact"


@pytest.mark.asyncio
async def test_get_code_artifact_not_found(test_code_artifact_service):
    user_id = uuid4()

    with pytest.raises(NotFoundError):
        await test_code_artifact_service.get_code_artifact(user_id, 999)


@pytest.mark.asyncio
async def test_list_code_artifacts(test_code_artifact_service):
    user_id = uuid4()

    # Create multiple artifacts
    for i in range(3):
        artifact_data = CodeArtifactCreate(
            title=f"Artifact {i}",
            description="Test",
            code=f"code_{i}",
            language="python",
            tags=["test"]
        )
        await test_code_artifact_service.create_code_artifact(user_id, artifact_data)

    # List
    artifacts = await test_code_artifact_service.list_code_artifacts(user_id)

    assert len(artifacts) == 3


@pytest.mark.asyncio
async def test_list_code_artifacts_filter_by_language(test_code_artifact_service):
    user_id = uuid4()

    # Create Python artifact
    await test_code_artifact_service.create_code_artifact(
        user_id,
        CodeArtifactCreate(title="Python", description="Test", code="code", language="python", tags=[])
    )

    # Create JavaScript artifact
    await test_code_artifact_service.create_code_artifact(
        user_id,
        CodeArtifactCreate(title="JS", description="Test", code="code", language="javascript", tags=[])
    )

    # Filter by Python
    python_artifacts = await test_code_artifact_service.list_code_artifacts(user_id, language="python")

    assert len(python_artifacts) == 1
    assert python_artifacts[0].language == "python"


@pytest.mark.asyncio
async def test_list_code_artifacts_filter_by_tags(test_code_artifact_service):
    user_id = uuid4()

    # Create with different tags
    await test_code_artifact_service.create_code_artifact(
        user_id,
        CodeArtifactCreate(title="Auth", description="Test", code="code", language="python", tags=["auth"])
    )

    await test_code_artifact_service.create_code_artifact(
        user_id,
        CodeArtifactCreate(title="DB", description="Test", code="code", language="python", tags=["database"])
    )

    # Filter by auth tag
    auth_artifacts = await test_code_artifact_service.list_code_artifacts(user_id, tags=["auth"])

    assert len(auth_artifacts) == 1
    assert "auth" in auth_artifacts[0].tags


@pytest.mark.asyncio
async def test_update_code_artifact(test_code_artifact_service):
    user_id = uuid4()

    # Create
    artifact_data = CodeArtifactCreate(
        title="Original",
        description="Original desc",
        code="original code",
        language="python",
        tags=["original"]
    )
    created = await test_code_artifact_service.create_code_artifact(user_id, artifact_data)

    # Update
    update_data = CodeArtifactUpdate(title="Updated", tags=["updated"])
    updated = await test_code_artifact_service.update_code_artifact(user_id, created.id, update_data)

    assert updated.title == "Updated"
    assert updated.description == "Original desc"  # Unchanged
    assert updated.tags == ["updated"]


@pytest.mark.asyncio
async def test_delete_code_artifact(test_code_artifact_service):
    user_id = uuid4()

    # Create
    artifact_data = CodeArtifactCreate(
        title="To Delete",
        description="Test",
        code="code",
        language="python",
        tags=[]
    )
    created = await test_code_artifact_service.create_code_artifact(user_id, artifact_data)

    # Delete
    success = await test_code_artifact_service.delete_code_artifact(user_id, created.id)
    assert success is True

    # Verify deleted
    with pytest.raises(NotFoundError):
        await test_code_artifact_service.get_code_artifact(user_id, created.id)
