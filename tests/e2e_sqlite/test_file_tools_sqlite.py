"""E2E tests for file MCP tools with sqlite-backed MCP server
"""
import base64

import pytest

# Test data
SMALL_FILE_DATA = base64.b64encode(b"Hello, World!").decode("utf-8")  # 13 bytes
PNG_HEADER = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode("utf-8")


@pytest.mark.asyncio
async def test_create_file_basic_e2e(mcp_client):
    """Test creating a file with all fields"""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "screenshot.png",
            "description": "Homepage screenshot for v2 design review",
            "data": PNG_HEADER,
            "mime_type": "image/png",
            "tags": ["screenshot", "ui", "v2"],
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["filename"] == "screenshot.png"
    assert result.data["description"] == "Homepage screenshot for v2 design review"
    assert result.data["mime_type"] == "image/png"
    assert result.data["tags"] == ["screenshot", "ui", "v2"]
    assert result.data["size_bytes"] == len(base64.b64decode(PNG_HEADER))
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.asyncio
async def test_get_file_e2e(mcp_client):
    """Test creating then retrieving a file"""
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "retrieve-test.txt",
            "description": "Test file for retrieval",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["test"],
        },
    })
    file_id = create_result.data["id"]

    get_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "get_file",
        "arguments": {"file_id": file_id},
    })
    assert get_result.data is not None
    assert get_result.data["id"] == file_id
    assert get_result.data["filename"] == "retrieve-test.txt"
    assert get_result.data["data"] == SMALL_FILE_DATA


@pytest.mark.asyncio
async def test_list_files_e2e(mcp_client):
    """Test listing files"""
    file_names = ["list-file-1.txt", "list-file-2.txt", "list-file-3.txt"]
    for name in file_names:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "create_file",
            "arguments": {
                "filename": name,
                "description": f"Description for {name}",
                "data": SMALL_FILE_DATA,
                "mime_type": "text/plain",
                "tags": ["list-test"],
            },
        })

    list_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "list_files",
        "arguments": {},
    })
    assert list_result.data is not None
    assert "files" in list_result.data
    assert "total_count" in list_result.data
    files = list_result.data["files"]
    assert len(files) >= 3
    filenames_in_result = [f["filename"] for f in files]
    for name in file_names:
        assert name in filenames_in_result


@pytest.mark.asyncio
async def test_list_files_filter_by_mime_type_e2e(mcp_client):
    """Test filtering files by MIME type"""
    # Create text file
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "plain.txt",
            "description": "A plain text file",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": [],
        },
    })

    # Create image file
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "photo.png",
            "description": "A PNG image",
            "data": PNG_HEADER,
            "mime_type": "image/png",
            "tags": [],
        },
    })

    # Filter by image/png
    list_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "list_files",
        "arguments": {"mime_type": "image/png"},
    })
    files = list_result.data["files"]
    assert len(files) >= 1
    for f in files:
        assert f["mime_type"] == "image/png"


@pytest.mark.asyncio
async def test_list_files_by_project_e2e(mcp_client):
    """Test filtering files by project_id"""
    # Create a project
    project_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_project",
        "arguments": {
            "name": "file-test-project",
            "description": "Project for file filtering",
            "project_type": "development",
        },
    })
    project_id = project_result.data["id"]

    # Create file without project
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "unlinked.txt",
            "description": "Not linked to project",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": [],
        },
    })

    # Create file with project
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "linked-to-project.txt",
            "description": "Linked to project",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": [],
            "project_id": project_id,
        },
    })

    # Filter by project
    list_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "list_files",
        "arguments": {"project_id": project_id},
    })
    files = list_result.data["files"]
    assert len(files) == 1
    assert files[0]["filename"] == "linked-to-project.txt"


@pytest.mark.asyncio
async def test_update_file_e2e(mcp_client):
    """Test updating a file (PATCH semantics)"""
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "original.txt",
            "description": "Original description",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": ["original"],
        },
    })
    file_id = create_result.data["id"]

    update_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "update_file",
        "arguments": {
            "file_id": file_id,
            "filename": "renamed.txt",
            "tags": ["updated", "renamed"],
        },
    })
    assert update_result.data["filename"] == "renamed.txt"
    assert update_result.data["description"] == "Original description"  # unchanged
    assert update_result.data["tags"] == ["updated", "renamed"]
    assert update_result.data["mime_type"] == "text/plain"  # unchanged


@pytest.mark.asyncio
async def test_delete_file_e2e(mcp_client):
    """Test deleting a file"""
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "to-delete.txt",
            "description": "Will be deleted",
            "data": SMALL_FILE_DATA,
            "mime_type": "text/plain",
            "tags": [],
        },
    })
    file_id = create_result.data["id"]

    delete_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "delete_file",
        "arguments": {
            "file_id": file_id,
        },
    })
    assert delete_result.data is not None
    assert delete_result.data["deleted_id"] == file_id

    # Verify deleted
    try:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "get_file",
            "arguments": {"file_id": file_id},
        })
        assert False, "Expected error for deleted file"
    except Exception as e:
        assert "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_text_file_round_trip_e2e(mcp_client):
    """Store a .txt file with realistic content including unicode, newlines,
    and special characters, retrieve it, and verify the content is identical.
    """
    original_text = (
        "Meeting Notes — 2026-03-15\n"
        "==========================\n\n"
        "Attendees: José, François, Müller, 田中太郎\n\n"
        "Key decisions:\n"
        "  1. Migrate auth service to OAuth 2.1 (deadline: Q2)\n"
        "  2. Budget approved: €50,000 for infrastructure\n"
        '  3. "Zero-downtime" deploy strategy confirmed ✓\n\n'
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
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "meeting-notes-2026-03-15.txt",
            "description": "Weekly sync meeting notes with unicode content",
            "data": original_b64,
            "mime_type": "text/plain; charset=utf-8",
            "tags": ["meeting-notes", "round-trip-test"],
        },
    })
    file_id = create_result.data["id"]
    assert create_result.data["size_bytes"] == len(original_bytes)

    # Retrieve
    get_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "get_file",
        "arguments": {"file_id": file_id},
    })

    # Decode and verify content is functionally intact
    retrieved_bytes = base64.b64decode(get_result.data["data"])
    retrieved_text = retrieved_bytes.decode("utf-8")

    assert retrieved_text == original_text
    assert len(retrieved_bytes) == len(original_bytes)
    assert get_result.data["size_bytes"] == len(original_bytes)


@pytest.mark.asyncio
async def test_get_file_not_found_e2e(mcp_client):
    """Test error handling for non-existent file"""
    try:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "get_file",
            "arguments": {"file_id": 999999},
        })
        assert False, "Expected error for non-existent file"
    except Exception as e:
        assert "not found" in str(e).lower()
