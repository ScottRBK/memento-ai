"""E2E tests for skill MCP tools with real PostgreSQL database
"""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


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
