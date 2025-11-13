"""
Integration tests for EntityService with in-memory stubs
"""
import pytest
from uuid import uuid4

from app.models.entity_models import EntityCreate, EntityUpdate, EntityType, EntityRelationshipCreate, EntityRelationshipUpdate
from app.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_entity(test_entity_service):
    user_id = uuid4()

    entity_data = EntityCreate(
        name="Acme Corp",
        entity_type=EntityType.ORGANIZATION,
        notes="A software company",
        tags=["tech", "b2b"]
    )

    entity = await test_entity_service.create_entity(user_id, entity_data)

    assert entity.id is not None
    assert entity.name == "Acme Corp"
    assert entity.entity_type == EntityType.ORGANIZATION
    assert entity.notes == "A software company"
    assert entity.tags == ["tech", "b2b"]


@pytest.mark.asyncio
async def test_create_entity_with_custom_type(test_entity_service):
    user_id = uuid4()

    entity_data = EntityCreate(
        name="IoT Sensor",
        entity_type=EntityType.OTHER,
        custom_type="Sensor",
        tags=["hardware"]
    )

    entity = await test_entity_service.create_entity(user_id, entity_data)

    assert entity.id is not None
    assert entity.entity_type == EntityType.OTHER
    assert entity.custom_type == "Sensor"


@pytest.mark.asyncio
async def test_get_entity(test_entity_service):
    user_id = uuid4()

    # Create
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityType.INDIVIDUAL,
        tags=[]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    # Get
    retrieved = await test_entity_service.get_entity(user_id, created.id)

    assert retrieved.id == created.id
    assert retrieved.name == "Test Entity"


@pytest.mark.asyncio
async def test_get_entity_not_found(test_entity_service):
    user_id = uuid4()

    with pytest.raises(NotFoundError):
        await test_entity_service.get_entity(user_id, 999)


@pytest.mark.asyncio
async def test_list_entities(test_entity_service):
    user_id = uuid4()

    # Create multiple entities
    for i in range(3):
        entity_data = EntityCreate(
            name=f"Entity {i}",
            entity_type=EntityType.ORGANIZATION,
            tags=["test"]
        )
        await test_entity_service.create_entity(user_id, entity_data)

    # List
    entities = await test_entity_service.list_entities(user_id)

    assert len(entities) == 3


@pytest.mark.asyncio
async def test_list_entities_filter_by_type(test_entity_service):
    user_id = uuid4()

    # Create different types
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Company", entity_type=EntityType.ORGANIZATION, tags=[])
    )

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Person", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    # Filter by organization
    orgs = await test_entity_service.list_entities(user_id, entity_type=EntityType.ORGANIZATION)

    assert len(orgs) == 1
    assert orgs[0].entity_type == EntityType.ORGANIZATION


@pytest.mark.asyncio
async def test_list_entities_filter_by_tags(test_entity_service):
    user_id = uuid4()

    # Create with different tags
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Dev Team", entity_type=EntityType.TEAM, tags=["engineering"])
    )

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Sales Team", entity_type=EntityType.TEAM, tags=["sales"])
    )

    # Filter by engineering tag
    eng_entities = await test_entity_service.list_entities(user_id, tags=["engineering"])

    assert len(eng_entities) == 1
    assert "engineering" in eng_entities[0].tags


@pytest.mark.asyncio
async def test_update_entity(test_entity_service):
    user_id = uuid4()

    # Create
    entity_data = EntityCreate(
        name="Original Name",
        entity_type=EntityType.ORGANIZATION,
        notes="Original notes",
        tags=["original"]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    # Update
    update_data = EntityUpdate(name="Updated Name", notes="New notes")
    updated = await test_entity_service.update_entity(user_id, created.id, update_data)

    assert updated.name == "Updated Name"
    assert updated.notes == "New notes"
    assert updated.tags == ["original"]  # Unchanged


@pytest.mark.asyncio
async def test_delete_entity(test_entity_service):
    user_id = uuid4()

    # Create
    entity_data = EntityCreate(
        name="To Delete",
        entity_type=EntityType.ORGANIZATION,
        tags=[]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    # Delete
    success = await test_entity_service.delete_entity(user_id, created.id)
    assert success is True

    # Verify deleted
    with pytest.raises(NotFoundError):
        await test_entity_service.get_entity(user_id, created.id)


@pytest.mark.asyncio
async def test_link_entity_to_memory(test_entity_service):
    user_id = uuid4()

    # Create entity
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityType.ORGANIZATION,
        tags=[]
    )
    entity = await test_entity_service.create_entity(user_id, entity_data)

    # Link to memory (memory_id = 1)
    success = await test_entity_service.link_entity_to_memory(user_id, entity.id, 1)
    assert success is True


@pytest.mark.asyncio
async def test_unlink_entity_from_memory(test_entity_service):
    user_id = uuid4()

    # Create entity
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityType.ORGANIZATION,
        tags=[]
    )
    entity = await test_entity_service.create_entity(user_id, entity_data)

    # Link
    await test_entity_service.link_entity_to_memory(user_id, entity.id, 1)

    # Unlink
    success = await test_entity_service.unlink_entity_from_memory(user_id, entity.id, 1)
    assert success is True


@pytest.mark.asyncio
async def test_create_entity_relationship(test_entity_service):
    user_id = uuid4()

    # Create two entities
    entity1 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 1", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    entity2 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 2", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    # Create relationship
    relationship_data = EntityRelationshipCreate(
        source_entity_id=entity1.id,
        target_entity_id=entity2.id,
        relationship_type="employs",
        strength=0.9,
        confidence=0.8,
        metadata={"role": "developer"}
    )

    relationship = await test_entity_service.create_entity_relationship(user_id, relationship_data)

    assert relationship.id is not None
    assert relationship.source_entity_id == entity1.id
    assert relationship.target_entity_id == entity2.id
    assert relationship.relationship_type == "employs"
    assert relationship.strength == 0.9
    assert relationship.confidence == 0.8
    assert relationship.metadata == {"role": "developer"}


@pytest.mark.asyncio
async def test_get_entity_relationships(test_entity_service):
    user_id = uuid4()

    # Create entities
    entity1 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 1", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    entity2 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 2", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    # Create relationship
    await test_entity_service.create_entity_relationship(
        user_id,
        EntityRelationshipCreate(
            source_entity_id=entity1.id,
            target_entity_id=entity2.id,
            relationship_type="employs"
        )
    )

    # Get relationships
    relationships = await test_entity_service.get_entity_relationships(user_id, entity1.id)

    assert len(relationships) == 1
    assert relationships[0].source_entity_id == entity1.id


@pytest.mark.asyncio
async def test_get_entity_relationships_filter_by_direction(test_entity_service):
    user_id = uuid4()

    # Create entities
    entity1 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 1", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    entity2 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 2", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    # Create relationship
    await test_entity_service.create_entity_relationship(
        user_id,
        EntityRelationshipCreate(
            source_entity_id=entity1.id,
            target_entity_id=entity2.id,
            relationship_type="employs"
        )
    )

    # Get outgoing relationships
    outgoing = await test_entity_service.get_entity_relationships(
        user_id, entity1.id, direction="outgoing"
    )
    assert len(outgoing) == 1

    # Get incoming relationships
    incoming = await test_entity_service.get_entity_relationships(
        user_id, entity1.id, direction="incoming"
    )
    assert len(incoming) == 0


@pytest.mark.asyncio
async def test_update_entity_relationship(test_entity_service):
    user_id = uuid4()

    # Create entities and relationship
    entity1 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 1", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    entity2 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 2", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    relationship = await test_entity_service.create_entity_relationship(
        user_id,
        EntityRelationshipCreate(
            source_entity_id=entity1.id,
            target_entity_id=entity2.id,
            relationship_type="employs",
            strength=0.5
        )
    )

    # Update
    update_data = EntityRelationshipUpdate(strength=0.9, metadata={"updated": True})
    updated = await test_entity_service.update_entity_relationship(
        user_id, relationship.id, update_data
    )

    assert updated.strength == 0.9
    assert updated.metadata == {"updated": True}
    assert updated.relationship_type == "employs"  # Unchanged


@pytest.mark.asyncio
async def test_delete_entity_relationship(test_entity_service):
    user_id = uuid4()

    # Create entities and relationship
    entity1 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 1", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    entity2 = await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Entity 2", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    relationship = await test_entity_service.create_entity_relationship(
        user_id,
        EntityRelationshipCreate(
            source_entity_id=entity1.id,
            target_entity_id=entity2.id,
            relationship_type="employs"
        )
    )

    # Delete
    success = await test_entity_service.delete_entity_relationship(user_id, relationship.id)
    assert success is True

    # Verify deleted
    relationships = await test_entity_service.get_entity_relationships(user_id, entity1.id)
    assert len(relationships) == 0
