"""
Integration tests for activity event emission across all services.

Tests verify that services emit the correct events when:
- CRUD operations occur (CREATED, UPDATED, DELETED)
- Read operations occur when ACTIVITY_TRACK_READS is enabled (READ, QUERIED)
"""
import pytest
from unittest.mock import patch
from uuid import uuid4

from app.config.settings import settings
from app.models.activity_models import EntityType, ActionType
from app.models.project_models import ProjectCreate, ProjectType, ProjectUpdate
from app.models.document_models import DocumentCreate
from app.models.code_artifact_models import CodeArtifactCreate
from app.models.entity_models import (
    EntityCreate,
    EntityType as EntityKind,
    EntityRelationshipCreate,
)


# ============================================================================
# Project Service Activity Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_project_create_emits_event(test_project_service_with_event_bus):
    """create_project() emits CREATED event."""
    service, event_bus = test_project_service_with_event_bus
    user_id = uuid4()

    project_data = ProjectCreate(
        name="Test Project",
        description="Test description",
        project_type=ProjectType.DEVELOPMENT,
    )
    project = await service.create_project(user_id, project_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.PROJECT
    assert event.entity_id == project.id
    assert event.action == ActionType.CREATED
    assert event.snapshot["name"] == "Test Project"


@pytest.mark.asyncio
async def test_project_update_emits_event_with_changes(test_project_service_with_event_bus):
    """update_project() emits UPDATED event with changes dict."""
    service, event_bus = test_project_service_with_event_bus
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="Original Name",
        description="Original description",
        project_type=ProjectType.DEVELOPMENT,
    )
    project = await service.create_project(user_id, project_data)
    event_bus.collected_events.clear()

    # Update project
    update_data = ProjectUpdate(name="Updated Name")
    await service.update_project(user_id, project.id, update_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.PROJECT
    assert event.action == ActionType.UPDATED
    assert event.changes is not None
    assert "name" in event.changes
    assert event.changes["name"]["old"] == "Original Name"
    assert event.changes["name"]["new"] == "Updated Name"


@pytest.mark.asyncio
async def test_project_delete_emits_event(test_project_service_with_event_bus):
    """delete_project() emits DELETED event with pre-deletion snapshot."""
    service, event_bus = test_project_service_with_event_bus
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="To Delete",
        description="Will be deleted",
        project_type=ProjectType.DEVELOPMENT,
    )
    project = await service.create_project(user_id, project_data)
    event_bus.collected_events.clear()

    # Delete project
    await service.delete_project(user_id, project.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.PROJECT
    assert event.action == ActionType.DELETED
    assert event.snapshot["name"] == "To Delete"


@pytest.mark.asyncio
async def test_project_read_emits_event_when_tracking_enabled(test_project_service_with_event_bus):
    """get_project() emits READ event when ACTIVITY_TRACK_READS=True."""
    service, event_bus = test_project_service_with_event_bus
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="Test Project",
        description="Test",
        project_type=ProjectType.DEVELOPMENT,
    )
    project = await service.create_project(user_id, project_data)
    event_bus.collected_events.clear()

    # Read with tracking enabled
    with patch.object(settings, 'ACTIVITY_TRACK_READS', True):
        await service.get_project(user_id, project.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.PROJECT
    assert event.action == ActionType.READ


@pytest.mark.asyncio
async def test_project_list_emits_queried_event(test_project_service_with_event_bus):
    """list_projects() emits QUERIED event when ACTIVITY_TRACK_READS=True."""
    service, event_bus = test_project_service_with_event_bus
    user_id = uuid4()

    # Create project
    project_data = ProjectCreate(
        name="Test Project",
        description="Test",
        project_type=ProjectType.DEVELOPMENT,
    )
    await service.create_project(user_id, project_data)
    event_bus.collected_events.clear()

    # List with tracking enabled
    with patch.object(settings, 'ACTIVITY_TRACK_READS', True):
        await service.list_projects(user_id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.PROJECT
    assert event.action == ActionType.QUERIED
    assert event.entity_id == 0  # Query spans multiple


# ============================================================================
# Document Service Activity Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_document_create_emits_event(test_document_service_with_event_bus):
    """create_document() emits CREATED event."""
    service, event_bus = test_document_service_with_event_bus
    user_id = uuid4()

    doc_data = DocumentCreate(
        title="Test Document",
        description="Test description",
        content="Document content",
        document_type="text",
        tags=["test"],
    )
    doc = await service.create_document(user_id, doc_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.DOCUMENT
    assert event.entity_id == doc.id
    assert event.action == ActionType.CREATED


@pytest.mark.asyncio
async def test_document_delete_emits_event(test_document_service_with_event_bus):
    """delete_document() emits DELETED event."""
    service, event_bus = test_document_service_with_event_bus
    user_id = uuid4()

    # Create document
    doc_data = DocumentCreate(
        title="To Delete",
        description="Test",
        content="Content",
        document_type="text",
        tags=["test"],
    )
    doc = await service.create_document(user_id, doc_data)
    event_bus.collected_events.clear()

    # Delete
    await service.delete_document(user_id, doc.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.DOCUMENT
    assert event.action == ActionType.DELETED


# ============================================================================
# Code Artifact Service Activity Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_code_artifact_create_emits_event(test_code_artifact_service_with_event_bus):
    """create_code_artifact() emits CREATED event."""
    service, event_bus = test_code_artifact_service_with_event_bus
    user_id = uuid4()

    artifact_data = CodeArtifactCreate(
        title="Test Artifact",
        description="Test description",
        code="def test(): pass",
        language="python",
        tags=["test"],
    )
    artifact = await service.create_code_artifact(user_id, artifact_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.CODE_ARTIFACT
    assert event.entity_id == artifact.id
    assert event.action == ActionType.CREATED


@pytest.mark.asyncio
async def test_code_artifact_delete_emits_event(test_code_artifact_service_with_event_bus):
    """delete_code_artifact() emits DELETED event."""
    service, event_bus = test_code_artifact_service_with_event_bus
    user_id = uuid4()

    # Create artifact
    artifact_data = CodeArtifactCreate(
        title="To Delete",
        description="Test",
        code="print('hello')",
        language="python",
        tags=["test"],
    )
    artifact = await service.create_code_artifact(user_id, artifact_data)
    event_bus.collected_events.clear()

    # Delete
    await service.delete_code_artifact(user_id, artifact.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.CODE_ARTIFACT
    assert event.action == ActionType.DELETED


# ============================================================================
# Entity Service Activity Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_entity_create_emits_event(test_entity_service_with_event_bus):
    """create_entity() emits CREATED event."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityKind.INDIVIDUAL,
        notes="Test notes",
        tags=["test"],
    )
    entity = await service.create_entity(user_id, entity_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.ENTITY
    assert event.entity_id == entity.id
    assert event.action == ActionType.CREATED


@pytest.mark.asyncio
async def test_entity_delete_emits_event(test_entity_service_with_event_bus):
    """delete_entity() emits DELETED event."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    # Create entity
    entity_data = EntityCreate(
        name="To Delete",
        entity_type=EntityKind.INDIVIDUAL,
        tags=["test"],
    )
    entity = await service.create_entity(user_id, entity_data)
    event_bus.collected_events.clear()

    # Delete
    await service.delete_entity(user_id, entity.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.ENTITY
    assert event.action == ActionType.DELETED


@pytest.mark.asyncio
async def test_entity_read_emits_event_when_tracking_enabled(test_entity_service_with_event_bus):
    """get_entity() emits READ event when ACTIVITY_TRACK_READS=True."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    # Create entity
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityKind.INDIVIDUAL,
        tags=["test"],
    )
    entity = await service.create_entity(user_id, entity_data)
    event_bus.collected_events.clear()

    # Read with tracking enabled
    with patch.object(settings, 'ACTIVITY_TRACK_READS', True):
        await service.get_entity(user_id, entity.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.ENTITY
    assert event.action == ActionType.READ


# ============================================================================
# Entity-Memory Link Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_entity_memory_link_emits_event(test_entity_service_with_event_bus):
    """link_entity_to_memory() emits ENTITY_MEMORY_LINK CREATED event."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    # Create entity
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityKind.INDIVIDUAL,
        tags=["test"],
    )
    entity = await service.create_entity(user_id, entity_data)
    event_bus.collected_events.clear()

    # Link entity to memory (mock repo doesn't verify memory exists, just stores link)
    memory_id = 1
    await service.link_entity_to_memory(user_id, entity.id, memory_id)

    # Find the link event
    link_events = [e for e in event_bus.collected_events if e.entity_type == EntityType.ENTITY_MEMORY_LINK]
    assert len(link_events) == 1
    event = link_events[0]
    assert event.action == ActionType.CREATED
    assert event.snapshot["entity_id"] == entity.id
    assert event.snapshot["memory_id"] == memory_id


# ============================================================================
# Entity Relationship Event Tests
# ============================================================================


@pytest.mark.asyncio
async def test_entity_relationship_create_emits_event(test_entity_service_with_event_bus):
    """create_entity_relationship() emits ENTITY_RELATIONSHIP CREATED event."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    # Create two entities
    entity1_data = EntityCreate(
        name="Entity 1",
        entity_type=EntityKind.INDIVIDUAL,
        tags=["test"],
    )
    entity1 = await service.create_entity(user_id, entity1_data)

    entity2_data = EntityCreate(
        name="Entity 2",
        entity_type=EntityKind.ORGANIZATION,
        tags=["test"],
    )
    entity2 = await service.create_entity(user_id, entity2_data)

    event_bus.collected_events.clear()

    # Create relationship
    rel_data = EntityRelationshipCreate(
        source_entity_id=entity1.id,
        target_entity_id=entity2.id,
        relationship_type="works_for",
    )
    relationship = await service.create_entity_relationship(user_id, rel_data)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.ENTITY_RELATIONSHIP
    assert event.entity_id == relationship.id
    assert event.action == ActionType.CREATED


@pytest.mark.asyncio
async def test_entity_relationship_delete_emits_event(test_entity_service_with_event_bus):
    """delete_entity_relationship() emits ENTITY_RELATIONSHIP DELETED event."""
    service, event_bus = test_entity_service_with_event_bus
    user_id = uuid4()

    # Create two entities and a relationship
    entity1_data = EntityCreate(
        name="Entity 1",
        entity_type=EntityKind.INDIVIDUAL,
        tags=["test"],
    )
    entity1 = await service.create_entity(user_id, entity1_data)

    entity2_data = EntityCreate(
        name="Entity 2",
        entity_type=EntityKind.ORGANIZATION,
        tags=["test"],
    )
    entity2 = await service.create_entity(user_id, entity2_data)

    rel_data = EntityRelationshipCreate(
        source_entity_id=entity1.id,
        target_entity_id=entity2.id,
        relationship_type="works_for",
    )
    relationship = await service.create_entity_relationship(user_id, rel_data)

    event_bus.collected_events.clear()

    # Delete relationship
    await service.delete_entity_relationship(user_id, relationship.id)

    assert len(event_bus.collected_events) == 1
    event = event_bus.collected_events[0]
    assert event.entity_type == EntityType.ENTITY_RELATIONSHIP
    assert event.action == ActionType.DELETED
    assert event.entity_id == relationship.id
