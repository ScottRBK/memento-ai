"""
Integration tests for FileService with in-memory stubs
"""
import base64

import pytest

from app.models.file_models import FileCreate, FileUpdate
from app.models.activity_models import EntityType, ActionType
from app.models.user_models import User
from app.exceptions import NotFoundError


@pytest.fixture
def test_user():
    """Provides a User with a UUID id."""
    return User(
        external_id="test-external-id",
        name="Test User",
        email="test@example.com",
    )


test_data = base64.b64encode(b"Hello, World!").decode("utf-8")


@pytest.mark.asyncio
async def test_create_file(test_file_service, test_user):
    file_data = FileCreate(
        filename="hello.txt",
        description="A greeting file",
        data=test_data,
        mime_type="text/plain",
        tags=["greeting", "test"],
    )

    file = await test_file_service.create_file(test_user.id, file_data)

    assert file.id is not None
    assert file.filename == "hello.txt"
    assert file.description == "A greeting file"
    assert file.data == test_data
    assert file.mime_type == "text/plain"
    assert file.tags == ["greeting", "test"]
    assert file.size_bytes == len(base64.b64decode(test_data))
    assert file.created_at is not None
    assert file.updated_at is not None


@pytest.mark.asyncio
async def test_get_file(test_file_service, test_user):
    file_data = FileCreate(
        filename="hello.txt",
        description="A greeting file",
        data=test_data,
        mime_type="text/plain",
        tags=["test"],
    )
    created = await test_file_service.create_file(test_user.id, file_data)

    retrieved = await test_file_service.get_file(test_user.id, created.id)

    assert retrieved.id == created.id
    assert retrieved.filename == "hello.txt"
    assert retrieved.data == test_data


@pytest.mark.asyncio
async def test_get_file_not_found(test_file_service, test_user):
    with pytest.raises(NotFoundError):
        await test_file_service.get_file(test_user.id, 999)


@pytest.mark.asyncio
async def test_list_files(test_file_service, test_user):
    for i in range(3):
        file_data = FileCreate(
            filename=f"file_{i}.txt",
            description=f"File number {i}",
            data=base64.b64encode(f"content {i}".encode()).decode("utf-8"),
            mime_type="text/plain",
            tags=["test"],
        )
        await test_file_service.create_file(test_user.id, file_data)

    files = await test_file_service.list_files(test_user.id)

    assert len(files) == 3
    # FileSummary should not have a data field
    for f in files:
        assert not hasattr(f, "data") or "data" not in f.model_fields


@pytest.mark.asyncio
async def test_list_files_filter_by_mime_type(test_file_service, test_user):
    await test_file_service.create_file(
        test_user.id,
        FileCreate(
            filename="image.png",
            description="An image",
            data=test_data,
            mime_type="image/png",
            tags=[],
        ),
    )
    await test_file_service.create_file(
        test_user.id,
        FileCreate(
            filename="doc.pdf",
            description="A PDF",
            data=test_data,
            mime_type="application/pdf",
            tags=[],
        ),
    )

    png_files = await test_file_service.list_files(test_user.id, mime_type="image/png")

    assert len(png_files) == 1
    assert png_files[0].mime_type == "image/png"


@pytest.mark.asyncio
async def test_list_files_filter_by_tags(test_file_service, test_user):
    await test_file_service.create_file(
        test_user.id,
        FileCreate(
            filename="screenshot.png",
            description="UI screenshot",
            data=test_data,
            mime_type="image/png",
            tags=["ui", "screenshot"],
        ),
    )
    await test_file_service.create_file(
        test_user.id,
        FileCreate(
            filename="spec.pdf",
            description="API spec",
            data=test_data,
            mime_type="application/pdf",
            tags=["api", "docs"],
        ),
    )

    ui_files = await test_file_service.list_files(test_user.id, tags=["ui"])

    assert len(ui_files) == 1
    assert "ui" in ui_files[0].tags


@pytest.mark.asyncio
async def test_update_file(test_file_service, test_user):
    file_data = FileCreate(
        filename="original.txt",
        description="Original description",
        data=test_data,
        mime_type="text/plain",
        tags=["original"],
    )
    created = await test_file_service.create_file(test_user.id, file_data)

    update_data = FileUpdate(filename="updated.txt", description="Updated description")
    updated = await test_file_service.update_file(test_user.id, created.id, update_data)

    assert updated.filename == "updated.txt"
    assert updated.description == "Updated description"
    assert updated.mime_type == "text/plain"  # Unchanged
    assert updated.tags == ["original"]  # Unchanged


@pytest.mark.asyncio
async def test_update_file_data(test_file_service, test_user):
    file_data = FileCreate(
        filename="data.bin",
        description="Binary data",
        data=test_data,
        mime_type="application/octet-stream",
        tags=[],
    )
    created = await test_file_service.create_file(test_user.id, file_data)
    original_size = created.size_bytes

    new_content = b"This is much longer content than Hello, World!"
    new_data = base64.b64encode(new_content).decode("utf-8")
    update_data = FileUpdate(data=new_data)
    updated = await test_file_service.update_file(test_user.id, created.id, update_data)

    assert updated.data == new_data
    assert updated.size_bytes == len(new_content)
    assert updated.size_bytes != original_size


@pytest.mark.asyncio
async def test_update_file_not_found(test_file_service, test_user):
    with pytest.raises(NotFoundError):
        await test_file_service.update_file(
            test_user.id, 999, FileUpdate(filename="nope.txt")
        )


@pytest.mark.asyncio
async def test_delete_file(test_file_service, test_user):
    file_data = FileCreate(
        filename="to_delete.txt",
        description="Will be deleted",
        data=test_data,
        mime_type="text/plain",
        tags=[],
    )
    created = await test_file_service.create_file(test_user.id, file_data)

    success = await test_file_service.delete_file(test_user.id, created.id)
    assert success is True

    with pytest.raises(NotFoundError):
        await test_file_service.get_file(test_user.id, created.id)


@pytest.mark.asyncio
async def test_delete_file_not_found(test_file_service, test_user):
    result = await test_file_service.delete_file(test_user.id, 999)
    assert result is False


@pytest.mark.asyncio
async def test_create_file_activity_events(test_file_service_with_event_bus, test_user):
    service, event_bus = test_file_service_with_event_bus

    file_data = FileCreate(
        filename="tracked.txt",
        description="Event tracking test",
        data=test_data,
        mime_type="text/plain",
        tags=["events"],
    )
    file = await service.create_file(test_user.id, file_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.FILE
    assert event.entity_id == file.id
    assert event.action == ActionType.CREATED
    assert event.snapshot["filename"] == "tracked.txt"


@pytest.mark.asyncio
async def test_update_file_activity_events(test_file_service_with_event_bus, test_user):
    service, event_bus = test_file_service_with_event_bus

    file_data = FileCreate(
        filename="original.txt",
        description="Original description",
        data=test_data,
        mime_type="text/plain",
        tags=["test"],
    )
    created = await service.create_file(test_user.id, file_data)
    event_bus.collected_events.clear()

    update_data = FileUpdate(filename="renamed.txt")
    await service.update_file(test_user.id, created.id, update_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.FILE
    assert event.action == ActionType.UPDATED
    assert event.changes is not None
    assert "filename" in event.changes
    assert event.changes["filename"]["old"] == "original.txt"
    assert event.changes["filename"]["new"] == "renamed.txt"
