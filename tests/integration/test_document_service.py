"""
Integration tests for DocumentService with in-memory stubs
"""
import pytest
from uuid import uuid4

from app.models.document_models import DocumentCreate, DocumentUpdate
from app.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_document(test_document_service):
    user_id = uuid4()

    document_data = DocumentCreate(
        title="API Documentation",
        description="REST API documentation",
        content="# API\n\nThis is the API documentation...",
        document_type="markdown",
        tags=["api", "docs"]
    )

    document = await test_document_service.create_document(user_id, document_data)

    assert document.id is not None
    assert document.title == "API Documentation"
    assert document.document_type == "markdown"
    assert document.size_bytes > 0


@pytest.mark.asyncio
async def test_get_document(test_document_service):
    user_id = uuid4()

    # Create
    document_data = DocumentCreate(
        title="Test Doc",
        description="Test",
        content="Content here",
        tags=[]
    )
    created = await test_document_service.create_document(user_id, document_data)

    # Get
    retrieved = await test_document_service.get_document(user_id, created.id)

    assert retrieved.id == created.id
    assert retrieved.title == "Test Doc"


@pytest.mark.asyncio
async def test_get_document_not_found(test_document_service):
    user_id = uuid4()

    with pytest.raises(NotFoundError):
        await test_document_service.get_document(user_id, 999)


@pytest.mark.asyncio
async def test_list_documents(test_document_service):
    user_id = uuid4()

    # Create multiple documents
    for i in range(3):
        document_data = DocumentCreate(
            title=f"Document {i}",
            description="Test",
            content=f"content_{i}",
            tags=["test"]
        )
        await test_document_service.create_document(user_id, document_data)

    # List
    documents = await test_document_service.list_documents(user_id)

    assert len(documents) == 3


@pytest.mark.asyncio
async def test_list_documents_filter_by_type(test_document_service):
    user_id = uuid4()

    # Create markdown document
    await test_document_service.create_document(
        user_id,
        DocumentCreate(title="MD", description="Test", content="content", document_type="markdown", tags=[])
    )

    # Create text document
    await test_document_service.create_document(
        user_id,
        DocumentCreate(title="TXT", description="Test", content="content", document_type="text", tags=[])
    )

    # Filter by markdown
    md_docs = await test_document_service.list_documents(user_id, document_type="markdown")

    assert len(md_docs) == 1
    assert md_docs[0].document_type == "markdown"


@pytest.mark.asyncio
async def test_list_documents_filter_by_tags(test_document_service):
    user_id = uuid4()

    # Create with different tags
    await test_document_service.create_document(
        user_id,
        DocumentCreate(title="Design", description="Test", content="content", tags=["design"])
    )

    await test_document_service.create_document(
        user_id,
        DocumentCreate(title="Code", description="Test", content="content", tags=["code"])
    )

    # Filter by design tag
    design_docs = await test_document_service.list_documents(user_id, tags=["design"])

    assert len(design_docs) == 1
    assert "design" in design_docs[0].tags


@pytest.mark.asyncio
async def test_update_document(test_document_service):
    user_id = uuid4()

    # Create
    document_data = DocumentCreate(
        title="Original",
        description="Original desc",
        content="original content",
        tags=["original"]
    )
    created = await test_document_service.create_document(user_id, document_data)

    # Update
    update_data = DocumentUpdate(title="Updated", content="new content")
    updated = await test_document_service.update_document(user_id, created.id, update_data)

    assert updated.title == "Updated"
    assert updated.content == "new content"
    assert updated.description == "Original desc"  # Unchanged
    assert updated.size_bytes == len("new content".encode('utf-8'))  # Recalculated


@pytest.mark.asyncio
async def test_delete_document(test_document_service):
    user_id = uuid4()

    # Create
    document_data = DocumentCreate(
        title="To Delete",
        description="Test",
        content="content",
        tags=[]
    )
    created = await test_document_service.create_document(user_id, document_data)

    # Delete
    success = await test_document_service.delete_document(user_id, created.id)
    assert success is True

    # Verify deleted
    with pytest.raises(NotFoundError):
        await test_document_service.get_document(user_id, created.id)
