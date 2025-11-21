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


@pytest.mark.asyncio
async def test_search_entities_basic(test_entity_service):
    """Test basic entity search by name"""
    user_id = uuid4()

    # Create entities with different names
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Tech Corp", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="TechFlow Inc", entity_type=EntityType.ORGANIZATION, tags=[])
    )
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Sarah Chen", entity_type=EntityType.INDIVIDUAL, tags=[])
    )

    # Search for "tech"
    results = await test_entity_service.search_entities(user_id, "tech")

    assert len(results) == 2
    assert all("tech" in e.name.lower() for e in results)


@pytest.mark.asyncio
async def test_search_entities_case_insensitive(test_entity_service):
    """Test that entity search is case-insensitive"""
    user_id = uuid4()

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="UPPERCASE ORG", entity_type=EntityType.ORGANIZATION, tags=[])
    )

    # Search with lowercase should still find it
    results = await test_entity_service.search_entities(user_id, "uppercase")

    assert len(results) == 1
    assert results[0].name == "UPPERCASE ORG"


@pytest.mark.asyncio
async def test_search_entities_with_type_filter(test_entity_service):
    """Test searching entities filtered by entity type"""
    user_id = uuid4()

    # Create different types
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Server Alpha", entity_type=EntityType.DEVICE, tags=[])
    )
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Server Beta", entity_type=EntityType.DEVICE, tags=[])
    )
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Server Team", entity_type=EntityType.TEAM, tags=[])
    )

    # Search for "server" but only devices
    results = await test_entity_service.search_entities(
        user_id,
        "server",
        entity_type=EntityType.DEVICE
    )

    assert len(results) == 2
    assert all(e.entity_type == EntityType.DEVICE for e in results)


@pytest.mark.asyncio
async def test_search_entities_with_tags_filter(test_entity_service):
    """Test searching entities filtered by tags"""
    user_id = uuid4()

    # Create entities with different tags
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Dev Server", entity_type=EntityType.DEVICE, tags=["production"])
    )
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Test Server", entity_type=EntityType.DEVICE, tags=["staging"])
    )

    # Search for "server" with production tag
    results = await test_entity_service.search_entities(
        user_id,
        "server",
        tags=["production"]
    )

    assert len(results) == 1
    assert "production" in results[0].tags


@pytest.mark.asyncio
async def test_search_entities_limit(test_entity_service):
    """Test that search respects limit parameter"""
    user_id = uuid4()

    # Create many entities
    for i in range(10):
        await test_entity_service.create_entity(
            user_id,
            EntityCreate(name=f"Test Entity {i}", entity_type=EntityType.ORGANIZATION, tags=[])
        )

    # Search with limit
    results = await test_entity_service.search_entities(user_id, "test", limit=3)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_search_entities_no_results(test_entity_service):
    """Test search returns empty list when no matches"""
    user_id = uuid4()

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(name="Acme Corp", entity_type=EntityType.ORGANIZATION, tags=[])
    )

    # Search for non-existent name
    results = await test_entity_service.search_entities(user_id, "nonexistent")

    assert len(results) == 0


# Entity-Project Many-to-Many Relationship Tests


@pytest.mark.asyncio
async def test_create_entity_with_multiple_projects(test_entity_service):
    """Test creating entity with multiple project associations"""
    user_id = uuid4()

    # Create entity with multiple projects
    entity_data = EntityCreate(
        name="Multi-Project Entity",
        entity_type=EntityType.ORGANIZATION,
        notes="Associated with multiple projects",
        tags=["multi-project"],
        project_ids=[1, 2, 3]
    )

    entity = await test_entity_service.create_entity(user_id, entity_data)

    assert entity.id is not None
    assert len(entity.project_ids) == 3
    assert 1 in entity.project_ids
    assert 2 in entity.project_ids
    assert 3 in entity.project_ids


@pytest.mark.asyncio
async def test_create_entity_with_no_projects(test_entity_service):
    """Test creating entity with no project associations"""
    user_id = uuid4()

    # Create entity without projects (None)
    entity_data = EntityCreate(
        name="No Project Entity",
        entity_type=EntityType.INDIVIDUAL,
        notes="No project associations",
        tags=["unassociated"],
        project_ids=None
    )

    entity = await test_entity_service.create_entity(user_id, entity_data)

    assert entity.id is not None
    assert len(entity.project_ids) == 0


@pytest.mark.asyncio
async def test_get_entity_with_project_ids(test_entity_service):
    """Test retrieving entity and verifying project_ids are loaded"""
    user_id = uuid4()

    # Create entity with projects
    entity_data = EntityCreate(
        name="Test Entity",
        entity_type=EntityType.ORGANIZATION,
        tags=["test"],
        project_ids=[10, 20]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    # Get entity and verify project_ids
    retrieved = await test_entity_service.get_entity(user_id, created.id)

    assert retrieved.id == created.id
    assert len(retrieved.project_ids) == 2
    assert 10 in retrieved.project_ids
    assert 20 in retrieved.project_ids


@pytest.mark.asyncio
async def test_list_entities_filter_by_project_ids(test_entity_service):
    """Test filtering entities by project_ids"""
    user_id = uuid4()

    # Create entities with different project associations
    await test_entity_service.create_entity(
        user_id,
        EntityCreate(
            name="Project 1 Entity",
            entity_type=EntityType.ORGANIZATION,
            tags=["proj-filter"],
            project_ids=[100]
        )
    )

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(
            name="Project 2 Entity",
            entity_type=EntityType.ORGANIZATION,
            tags=["proj-filter"],
            project_ids=[200]
        )
    )

    await test_entity_service.create_entity(
        user_id,
        EntityCreate(
            name="Multi Project Entity",
            entity_type=EntityType.ORGANIZATION,
            tags=["proj-filter"],
            project_ids=[100, 200]
        )
    )

    # Filter by project 100
    entities_in_proj100 = await test_entity_service.list_entities(
        user_id,
        project_ids=[100]
    )

    # Should find 2 entities (one with project 100, one with both 100 and 200)
    proj_filter_entities = [e for e in entities_in_proj100 if "proj-filter" in e.tags]
    assert len(proj_filter_entities) == 2

    # Filter by project 200
    entities_in_proj200 = await test_entity_service.list_entities(
        user_id,
        project_ids=[200]
    )

    proj_filter_entities_200 = [e for e in entities_in_proj200 if "proj-filter" in e.tags]
    assert len(proj_filter_entities_200) == 2


@pytest.mark.asyncio
async def test_update_entity_change_projects(test_entity_service):
    """Test updating entity to change project associations"""
    user_id = uuid4()

    # Create entity with initial projects
    entity_data = EntityCreate(
        name="Project Update Entity",
        entity_type=EntityType.ORGANIZATION,
        notes="Testing project updates",
        tags=["update-test"],
        project_ids=[1, 2]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    assert len(created.project_ids) == 2

    # Update to change projects (remove 1, keep 2, add 3)
    update_data = EntityUpdate(project_ids=[2, 3])
    updated = await test_entity_service.update_entity(user_id, created.id, update_data)

    assert len(updated.project_ids) == 2
    assert 2 in updated.project_ids
    assert 3 in updated.project_ids
    assert 1 not in updated.project_ids


@pytest.mark.asyncio
async def test_update_entity_clear_all_projects(test_entity_service):
    """Test updating entity to clear all project associations"""
    user_id = uuid4()

    # Create entity with projects
    entity_data = EntityCreate(
        name="Clear Projects Entity",
        entity_type=EntityType.ORGANIZATION,
        tags=["clear-test"],
        project_ids=[1, 2, 3]
    )
    created = await test_entity_service.create_entity(user_id, entity_data)

    assert len(created.project_ids) == 3

    # Update to clear all projects
    update_data = EntityUpdate(project_ids=[])
    updated = await test_entity_service.update_entity(user_id, created.id, update_data)

    assert len(updated.project_ids) == 0
