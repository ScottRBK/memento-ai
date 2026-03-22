"""E2E tests for skill MCP tools with real PostgreSQL database
"""
import base64

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

TINY_FILE_B64 = base64.b64encode(b"skill-link-test").decode("utf-8")


@pytest.mark.e2e
async def test_create_skill_e2e(mcp_client):
    """Test creating a skill with all fields"""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": "code-review",
            "description": "Systematic code review process for pull requests",
            "content": "# Code Review\n\n## Steps\n1. Check for security issues\n2. Review naming conventions",
            "tags": ["development", "review", "quality"],
            "importance": 8,
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["name"] == "code-review"
    assert result.data["description"] == "Systematic code review process for pull requests"
    assert result.data["content"] == "# Code Review\n\n## Steps\n1. Check for security issues\n2. Review naming conventions"
    assert result.data["tags"] == ["development", "review", "quality"]
    assert result.data["importance"] == 8
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.e2e
async def test_list_skills_e2e(mcp_client):
    """Test listing skills"""
    skill_names = ["list-skill-1", "list-skill-2", "list-skill-3"]
    for name in skill_names:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "create_skill",
            "arguments": {
                "name": name,
                "description": f"Description for {name}",
                "content": f"Content for {name}",
                "tags": ["list-test"],
                "importance": 7,
            },
        })

    list_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "list_skills",
        "arguments": {},
    })
    assert list_result.data is not None
    assert "skills" in list_result.data
    assert "total_count" in list_result.data
    skills = list_result.data["skills"]
    assert len(skills) >= 3
    skill_names_in_result = [s["name"] for s in skills]
    for name in skill_names:
        assert name in skill_names_in_result


@pytest.mark.e2e
async def test_search_skills_e2e(mcp_client):
    """Test semantic search across skills"""
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": "deploy-staging",
            "description": "Deploy application to staging environment using Docker and kubectl",
            "content": "# Staging Deployment\n\n## Prerequisites\nDocker and kubectl installed",
            "tags": ["deployment"],
            "importance": 8,
        },
    })
    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": "write-unit-tests",
            "description": "Write comprehensive unit tests using pytest framework",
            "content": "# Unit Testing\n\n## Steps\n1. Create test file\n2. Write test cases",
            "tags": ["testing"],
            "importance": 7,
        },
    })

    search_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "search_skills",
        "arguments": {"query": "deploy to staging with docker"},
    })
    assert search_result.data is not None
    assert "skills" in search_result.data
    assert "total_count" in search_result.data
    skills = search_result.data["skills"]
    assert len(skills) >= 1
    assert skills[0]["name"] == "deploy-staging"


@pytest.mark.e2e
async def test_update_skill_e2e(mcp_client):
    """Test updating a skill (PATCH semantics)"""
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": "update-test-skill",
            "description": "Original description",
            "content": "Original content",
            "tags": ["original"],
            "importance": 7,
        },
    })
    skill_id = create_result.data["id"]

    update_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "update_skill",
        "arguments": {
            "skill_id": skill_id,
            "description": "Updated description",
            "content": "Updated content here",
        },
    })
    assert update_result.data["description"] == "Updated description"
    assert update_result.data["name"] == "update-test-skill"
    assert update_result.data["content"] == "Updated content here"
    assert update_result.data["tags"] == ["original"]


@pytest.mark.e2e
async def test_delete_skill_e2e(mcp_client):
    """Test deleting a skill"""
    create_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": "to-delete-skill",
            "description": "Will be deleted",
            "content": "Delete this skill",
            "tags": [],
            "importance": 7,
        },
    })
    skill_id = create_result.data["id"]

    delete_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "delete_skill",
        "arguments": {"skill_id": skill_id},
    })
    assert delete_result.data is not None
    assert delete_result.data["deleted_id"] == skill_id

    try:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "get_skill",
            "arguments": {"skill_id": skill_id},
        })
        assert False, "Expected error for deleted skill"
    except Exception as e:
        assert "not found" in str(e).lower()


@pytest.mark.e2e
async def test_import_export_roundtrip_e2e(mcp_client):
    """Test that importing and exporting preserves key fields"""
    original_md = """---
name: roundtrip-skill
description: Roundtrip test skill for Postgres E2E
license: MIT
compatibility: Requires Python 3.12+
allowed-tools:
  - Read
  - Bash
---

# Roundtrip Skill

## Instructions
1. Step one
2. Step two
"""
    import_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "import_skill",
        "arguments": {
            "skill_md_content": original_md,
            "importance": 9,
        },
    })
    skill_id = import_result.data["id"]
    assert import_result.data["name"] == "roundtrip-skill"
    assert import_result.data["license"] == "MIT"
    assert import_result.data["importance"] == 9

    export_result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "export_skill",
        "arguments": {"skill_id": skill_id},
    })
    # export_skill returns a plain string, so access via content[0].text
    exported = export_result.content[0].text
    assert "name: roundtrip-skill" in exported
    assert "description: Roundtrip test skill for Postgres E2E" in exported
    assert "license: MIT" in exported
    assert "# Roundtrip Skill" in exported


# ---- Resource linking E2E tests ----


async def _create_skill_for_linking(mcp_client, suffix=""):
    """Helper to create a skill and return its ID."""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_skill",
        "arguments": {
            "name": f"link-e2e-skill{suffix}",
            "description": "Skill for resource linking E2E tests",
            "content": "# Link Test Skill",
            "tags": ["link-test"],
            "importance": 7,
        },
    })
    return result.data["id"]


async def _create_file_for_linking(mcp_client):
    """Helper to create a file and return its ID."""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_file",
        "arguments": {
            "filename": "skill-link-test.txt",
            "description": "File for skill linking E2E test",
            "data": TINY_FILE_B64,
            "mime_type": "text/plain",
            "tags": ["link-test"],
        },
    })
    return result.data["id"]


async def _create_code_artifact_for_linking(mcp_client):
    """Helper to create a code artifact and return its ID."""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_code_artifact",
        "arguments": {
            "title": "Skill Link Test Artifact",
            "description": "Code artifact for skill linking E2E test",
            "code": "def test(): pass",
            "language": "python",
            "tags": ["link-test"],
        },
    })
    return result.data["id"]


async def _create_document_for_linking(mcp_client):
    """Helper to create a document and return its ID."""
    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "create_document",
        "arguments": {
            "title": "Skill Link Test Document",
            "description": "Document for skill linking E2E test",
            "content": "This is a test document for skill linking.",
            "document_type": "analysis",
            "tags": ["link-test"],
        },
    })
    return result.data["id"]


@pytest.mark.e2e
async def test_link_skill_to_file_e2e(mcp_client):
    """Test linking a skill to a file via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-file")
    file_id = await _create_file_for_linking(mcp_client)

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_file",
        "arguments": {"skill_id": skill_id, "file_id": file_id},
    })
    assert result.data is not None
    assert result.data["skill_id"] == skill_id
    assert result.data["file_id"] == file_id
    assert result.data["linked"] is True


@pytest.mark.e2e
async def test_unlink_skill_from_file_e2e(mcp_client):
    """Test unlinking a skill from a file via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-unfile")
    file_id = await _create_file_for_linking(mcp_client)

    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_file",
        "arguments": {"skill_id": skill_id, "file_id": file_id},
    })

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "unlink_skill_from_file",
        "arguments": {"skill_id": skill_id, "file_id": file_id},
    })
    assert result.data is not None
    assert result.data["unlinked"] is True


@pytest.mark.e2e
async def test_link_skill_to_code_artifact_e2e(mcp_client):
    """Test linking a skill to a code artifact via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-ca")
    ca_id = await _create_code_artifact_for_linking(mcp_client)

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_code_artifact",
        "arguments": {"skill_id": skill_id, "code_artifact_id": ca_id},
    })
    assert result.data is not None
    assert result.data["skill_id"] == skill_id
    assert result.data["code_artifact_id"] == ca_id
    assert result.data["linked"] is True


@pytest.mark.e2e
async def test_unlink_skill_from_code_artifact_e2e(mcp_client):
    """Test unlinking a skill from a code artifact via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-unca")
    ca_id = await _create_code_artifact_for_linking(mcp_client)

    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_code_artifact",
        "arguments": {"skill_id": skill_id, "code_artifact_id": ca_id},
    })

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "unlink_skill_from_code_artifact",
        "arguments": {"skill_id": skill_id, "code_artifact_id": ca_id},
    })
    assert result.data is not None
    assert result.data["unlinked"] is True


@pytest.mark.e2e
async def test_link_skill_to_document_e2e(mcp_client):
    """Test linking a skill to a document via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-doc")
    doc_id = await _create_document_for_linking(mcp_client)

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_document",
        "arguments": {"skill_id": skill_id, "document_id": doc_id},
    })
    assert result.data is not None
    assert result.data["skill_id"] == skill_id
    assert result.data["document_id"] == doc_id
    assert result.data["linked"] is True


@pytest.mark.e2e
async def test_unlink_skill_from_document_e2e(mcp_client):
    """Test unlinking a skill from a document via MCP tool."""
    skill_id = await _create_skill_for_linking(mcp_client, "-undoc")
    doc_id = await _create_document_for_linking(mcp_client)

    await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "link_skill_to_document",
        "arguments": {"skill_id": skill_id, "document_id": doc_id},
    })

    result = await mcp_client.call_tool("execute_forgetful_tool", {
        "tool_name": "unlink_skill_from_document",
        "arguments": {"skill_id": skill_id, "document_id": doc_id},
    })
    assert result.data is not None
    assert result.data["unlinked"] is True


@pytest.mark.e2e
async def test_link_skill_to_file_skill_not_found_e2e(mcp_client):
    """Test linking a file to non-existent skill raises error."""
    try:
        await mcp_client.call_tool("execute_forgetful_tool", {
            "tool_name": "link_skill_to_file",
            "arguments": {"skill_id": 99999, "file_id": 1},
        })
        assert False, "Expected error for non-existent skill"
    except Exception as e:
        assert "not found" in str(e).lower()
