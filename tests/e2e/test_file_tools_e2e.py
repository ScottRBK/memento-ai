"""E2E tests for File tools with real PostgreSQL backend"""
import base64
import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio(loop_scope="session"),
]

# Disable auto-linking to keep memory creation deterministic
SETTINGS_OVERRIDE = {'MEMORY_NUM_AUTO_LINK': 0}

# Small PNG (1x1 transparent pixel) for test data
TINY_PNG_B64 = base64.b64encode(
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
    b'\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
).decode("utf-8")

# Different content for update tests
TINY_GIF_B64 = base64.b64encode(
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
    b'\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,'
    b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
).decode("utf-8")


async def test_create_file(mcp_client):
    """Test creating a file via tool, verify response"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'test-image.png',
            'description': 'A tiny test image',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['test', 'screenshot'],
        }
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["filename"] == 'test-image.png'
    assert result.data["description"] == 'A tiny test image'
    assert result.data["mime_type"] == 'image/png'
    assert result.data["tags"] == ['test', 'screenshot']
    assert result.data["size_bytes"] > 0
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


async def test_get_file(mcp_client):
    """Test creating then retrieving a file, verify base64 data round-trip"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'roundtrip.png',
            'description': 'File for get test',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['roundtrip'],
        }
    })
    file_id = create_result.data["id"]

    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_file',
        'arguments': {'file_id': file_id}
    })
    assert get_result.data is not None
    assert get_result.data["id"] == file_id
    assert get_result.data["filename"] == 'roundtrip.png'
    assert get_result.data["data"] == TINY_PNG_B64


async def test_list_files(mcp_client):
    """Test creating multiple files, listing, and verifying summaries"""
    filenames = ['list-test-1.png', 'list-test-2.pdf', 'list-test-3.txt']
    for filename in filenames:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_file',
            'arguments': {
                'filename': filename,
                'description': f'Description for {filename}',
                'data': TINY_PNG_B64,
                'mime_type': 'application/octet-stream',
                'tags': ['list-test'],
            }
        })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_files',
        'arguments': {}
    })
    assert list_result.data is not None
    assert 'files' in list_result.data
    assert 'total_count' in list_result.data
    files = list_result.data['files']
    assert len(files) >= 3

    listed_filenames = [f['filename'] for f in files]
    for filename in filenames:
        assert filename in listed_filenames


async def test_list_files_filter_mime_type(mcp_client):
    """Test filtering files by mime_type"""
    # Create files with different MIME types
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'mime-filter-image.png',
            'description': 'An image file',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['mime-test'],
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'mime-filter-doc.pdf',
            'description': 'A PDF file',
            'data': TINY_PNG_B64,
            'mime_type': 'application/pdf',
            'tags': ['mime-test'],
        }
    })

    # Filter for image/png only
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_files',
        'arguments': {'mime_type': 'image/png'}
    })
    files = list_result.data['files']
    assert len(files) >= 1
    for f in files:
        assert f['mime_type'] == 'image/png'


async def test_list_files_filter_tags(mcp_client):
    """Test filtering files by tags (GIN array overlap in Postgres)"""
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'tag-filter-a.png',
            'description': 'File with alpha tag',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['alpha', 'unique-tag-filter-test'],
        }
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'tag-filter-b.png',
            'description': 'File with beta tag',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['beta'],
        }
    })

    # Filter for 'unique-tag-filter-test' - should only match the first file
    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_files',
        'arguments': {'tags': ['unique-tag-filter-test']}
    })
    files = list_result.data['files']
    assert len(files) >= 1
    filenames = [f['filename'] for f in files]
    assert 'tag-filter-a.png' in filenames
    assert 'tag-filter-b.png' not in filenames


async def test_update_file(mcp_client):
    """Test updating file metadata (filename, description)"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'original-name.png',
            'description': 'Original description',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['original'],
        }
    })
    file_id = create_result.data["id"]

    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_file',
        'arguments': {
            'file_id': file_id,
            'filename': 'updated-name.png',
            'description': 'Updated description',
        }
    })
    assert update_result.data["filename"] == 'updated-name.png'
    assert update_result.data["description"] == 'Updated description'
    # Unchanged fields should be preserved
    assert update_result.data["mime_type"] == 'image/png'
    assert update_result.data["tags"] == ['original']


async def test_update_file_data(mcp_client):
    """Test updating file data content, verify size_bytes changes"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'data-update.png',
            'description': 'File to have its data replaced',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': [],
        }
    })
    file_id = create_result.data["id"]
    original_size = create_result.data["size_bytes"]

    # Update with different data (GIF is a different size)
    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_file',
        'arguments': {
            'file_id': file_id,
            'data': TINY_GIF_B64,
            'mime_type': 'image/gif',
        }
    })
    assert update_result.data["size_bytes"] != original_size
    assert update_result.data["mime_type"] == 'image/gif'

    # Verify round-trip by retrieving
    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_file',
        'arguments': {'file_id': file_id}
    })
    assert get_result.data["data"] == TINY_GIF_B64


async def test_delete_file(mcp_client):
    """Test creating then deleting a file"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'to-delete.png',
            'description': 'Will be deleted',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': [],
        }
    })
    file_id = create_result.data["id"]

    delete_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'delete_file',
        'arguments': {'file_id': file_id}
    })
    assert delete_result.data is not None
    assert delete_result.data['deleted_id'] == file_id

    # Verify it's gone
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_file',
            'arguments': {'file_id': file_id}
        })
        assert False, 'Expected error for deleted file'
    except Exception as e:
        assert 'not found' in str(e).lower()


async def test_create_memory_with_file_ids(mcp_client, postgres_app):
    """Create a file, then a memory linking to it via service layer, verify association.

    Note: file_ids is not yet wired through the MCP tool adapter for create_memory,
    so this test exercises the repository/service layer directly to validate the
    memory_file_association table works correctly in Postgres.
    """
    # Create a file via MCP tool
    file_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'memory-linked.png',
            'description': 'File to be linked to a memory',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['memory-link-test'],
        }
    })
    file_id = file_result.data["id"]

    # Create a memory with file_ids via the service layer directly
    # (file_ids not exposed through MCP tool adapter yet)
    from app.models.memory_models import MemoryCreate
    from app.models.user_models import UserCreate
    from app.config.settings import settings

    # Get the default user (auth is disabled in tests)
    user = await postgres_app.user_service.get_or_create_user(
        UserCreate(
            external_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            email=settings.DEFAULT_USER_EMAIL,
        )
    )

    memory_data = MemoryCreate(
        title='Memory with file link',
        content='This memory is linked to a file for testing.',
        context='E2E test for memory-file association',
        keywords=['file', 'association'],
        tags=['e2e-test'],
        importance=7,
        file_ids=[file_id],
    )

    memory, _ = await postgres_app.memory_service.create_memory(
        user_id=user.id,
        memory_data=memory_data,
    )

    assert file_id in memory.file_ids

    # Verify via get_memory that the association persists
    retrieved = await postgres_app.memory_service.get_memory(
        user_id=user.id,
        memory_id=memory.id,
    )
    assert file_id in retrieved.file_ids


async def test_text_file_round_trip(mcp_client):
    """Store a .txt file with realistic content including unicode, newlines,
    and special characters, retrieve it, and verify the content is identical."""
    original_text = (
        "Meeting Notes — 2026-03-15\n"
        "==========================\n\n"
        "Attendees: José, François, Müller, 田中太郎\n\n"
        "Key decisions:\n"
        "  1. Migrate auth service to OAuth 2.1 (deadline: Q2)\n"
        "  2. Budget approved: €50,000 for infrastructure\n"
        "  3. \"Zero-downtime\" deploy strategy confirmed ✓\n\n"
        "Action items:\n"
        "  • José → draft RFC by Friday\n"
        "  • François → benchmark latency (target: <50ms p99)\n"
        "  • Müller → review security audit findings\n\n"
        "Notes: The café near the office closes at 5pm — "
        "let's schedule syncs before then.\n"
        "Emoji test: 🚀 📊 ⚠️ ✅\n"
        "Special chars: tab→\there, backslash→\\, quotes→'\"'\n"
    )
    original_bytes = original_text.encode("utf-8")
    original_b64 = base64.b64encode(original_bytes).decode("utf-8")

    # Store
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'meeting-notes-2026-03-15.txt',
            'description': 'Weekly sync meeting notes with unicode content',
            'data': original_b64,
            'mime_type': 'text/plain; charset=utf-8',
            'tags': ['meeting-notes', 'round-trip-test'],
        }
    })
    file_id = create_result.data["id"]
    assert create_result.data["size_bytes"] == len(original_bytes)

    # Retrieve
    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_file',
        'arguments': {'file_id': file_id}
    })

    # Decode and verify content is functionally intact
    retrieved_bytes = base64.b64decode(get_result.data["data"])
    retrieved_text = retrieved_bytes.decode("utf-8")

    assert retrieved_text == original_text
    assert len(retrieved_bytes) == len(original_bytes)
    assert get_result.data["size_bytes"] == len(original_bytes)


async def test_file_summary_excludes_data(mcp_client):
    """Verify list response (FileSummary) doesn't include the data field"""
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_file',
        'arguments': {
            'filename': 'summary-test.png',
            'description': 'File for summary exclusion test',
            'data': TINY_PNG_B64,
            'mime_type': 'image/png',
            'tags': ['summary-test'],
        }
    })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_files',
        'arguments': {}
    })
    files = list_result.data['files']
    assert len(files) >= 1

    for f in files:
        # FileSummary should not contain the 'data' field
        assert 'data' not in f
        # But should contain summary fields
        assert 'id' in f
        assert 'filename' in f
        assert 'description' in f
        assert 'mime_type' in f
        assert 'size_bytes' in f
        assert 'tags' in f
