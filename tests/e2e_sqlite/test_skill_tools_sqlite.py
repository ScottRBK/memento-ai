"""
E2E tests for skill MCP tools with sqlite-backed MCP server
"""
import pytest


@pytest.mark.asyncio
async def test_create_skill(mcp_client):
    """Test creating a skill with valid kebab-case name and all fields"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'code-review',
            'description': 'Systematic code review process for pull requests',
            'content': '# Code Review\n\n## Steps\n1. Check for security issues\n2. Review naming conventions',
            'tags': ['development', 'review', 'quality'],
            'importance': 8,
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["name"] == 'code-review'
    assert result.data["description"] == 'Systematic code review process for pull requests'
    assert result.data["content"] == '# Code Review\n\n## Steps\n1. Check for security issues\n2. Review naming conventions'
    assert result.data["tags"] == ['development', 'review', 'quality']
    assert result.data["importance"] == 8
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


@pytest.mark.asyncio
async def test_get_skill(mcp_client):
    """Test creating then retrieving a skill by ID"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'get-test-skill',
            'description': 'A skill for testing retrieval',
            'content': '# Get Test\n\nThis skill is for testing the get endpoint.',
            'tags': ['test'],
            'importance': 7,
        },
    })
    skill_id = create_result.data["id"]

    get_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'get_skill',
        'arguments': {'skill_id': skill_id},
    })
    assert get_result.data is not None
    assert get_result.data["id"] == skill_id
    assert get_result.data["name"] == 'get-test-skill'
    assert get_result.data["description"] == 'A skill for testing retrieval'
    assert get_result.data["content"] == '# Get Test\n\nThis skill is for testing the get endpoint.'


@pytest.mark.asyncio
async def test_list_skills(mcp_client):
    """Test listing skills returns count and summaries without content"""
    skill_names = ['list-skill-1', 'list-skill-2', 'list-skill-3']
    for name in skill_names:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_skill',
            'arguments': {
                'name': name,
                'description': f'Description for {name}',
                'content': f'Content for {name}',
                'tags': ['list-test'],
                'importance': 7,
            },
        })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_skills',
        'arguments': {},
    })
    assert list_result.data is not None
    assert 'skills' in list_result.data
    assert 'total_count' in list_result.data
    skills = list_result.data['skills']
    assert len(skills) >= 3
    skill_names_in_result = [s['name'] for s in skills]
    for name in skill_names:
        assert name in skill_names_in_result
    # Summaries should not include content field
    for skill_summary in skills:
        assert 'content' not in skill_summary


@pytest.mark.asyncio
async def test_list_skills_filter_by_tags(mcp_client):
    """Test filtering skills by tags"""
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'tagged-alpha',
            'description': 'Skill with alpha tag',
            'content': 'Alpha content',
            'tags': ['alpha'],
            'importance': 7,
        },
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'tagged-beta',
            'description': 'Skill with beta tag',
            'content': 'Beta content',
            'tags': ['beta'],
            'importance': 7,
        },
    })

    list_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'list_skills',
        'arguments': {'tags': ['alpha']},
    })
    skills = list_result.data['skills']
    assert len(skills) >= 1
    skill_names_in_result = [s['name'] for s in skills]
    assert 'tagged-alpha' in skill_names_in_result
    assert 'tagged-beta' not in skill_names_in_result


@pytest.mark.asyncio
async def test_update_skill(mcp_client):
    """Test updating a skill (PATCH semantics - only provided fields changed)"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'update-test-skill',
            'description': 'Original description',
            'content': 'Original content here',
            'tags': ['original'],
            'importance': 7,
        },
    })
    skill_id = create_result.data["id"]

    update_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'update_skill',
        'arguments': {
            'skill_id': skill_id,
            'description': 'Updated description',
        },
    })
    assert update_result.data["description"] == 'Updated description'
    # Unchanged fields should be preserved
    assert update_result.data["name"] == 'update-test-skill'
    assert update_result.data["content"] == 'Original content here'
    assert update_result.data["tags"] == ['original']
    assert update_result.data["importance"] == 7


@pytest.mark.asyncio
async def test_delete_skill(mcp_client):
    """Test deleting a skill and verifying it's gone"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'to-delete-skill',
            'description': 'Will be deleted',
            'content': 'Delete this skill',
            'tags': [],
            'importance': 7,
        },
    })
    skill_id = create_result.data["id"]

    delete_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'delete_skill',
        'arguments': {'skill_id': skill_id},
    })
    assert delete_result.data is not None
    assert delete_result.data['deleted_id'] == skill_id

    try:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'get_skill',
            'arguments': {'skill_id': skill_id},
        })
        assert False, 'Expected error for deleted skill'
    except Exception as e:
        assert 'not found' in str(e).lower()


@pytest.mark.asyncio
async def test_search_skills(mcp_client):
    """Test semantic search across skills"""
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'deploy-staging',
            'description': 'Deploy application to staging environment using Docker and kubectl',
            'content': '# Staging Deployment\n\n## Prerequisites\nDocker and kubectl installed',
            'tags': ['deployment'],
            'importance': 8,
        },
    })
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'write-unit-tests',
            'description': 'Write comprehensive unit tests using pytest framework',
            'content': '# Unit Testing\n\n## Steps\n1. Create test file\n2. Write test cases',
            'tags': ['testing'],
            'importance': 7,
        },
    })

    search_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'search_skills',
        'arguments': {'query': 'deploy to staging with docker'},
    })
    assert search_result.data is not None
    assert 'skills' in search_result.data
    assert 'total_count' in search_result.data
    skills = search_result.data['skills']
    assert len(skills) >= 1
    # The deployment skill should be ranked first
    assert skills[0]['name'] == 'deploy-staging'


@pytest.mark.asyncio
async def test_import_skill(mcp_client):
    """Test importing a skill from SKILL.md format (YAML frontmatter + markdown body)"""
    skill_md = """---
name: imported-skill
description: An imported skill for testing
license: MIT
allowed-tools:
  - Read
  - Grep
---

# Imported Skill

## Steps
1. First step
2. Second step
"""
    result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'import_skill',
        'arguments': {
            'skill_md_content': skill_md,
            'importance': 8,
        },
    })
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["name"] == 'imported-skill'
    assert result.data["description"] == 'An imported skill for testing'
    assert result.data["license"] == 'MIT'
    assert result.data["allowed_tools"] == ['Read', 'Grep']
    assert result.data["importance"] == 8
    assert '# Imported Skill' in result.data["content"]


@pytest.mark.asyncio
async def test_export_skill(mcp_client):
    """Test exporting a skill to SKILL.md format"""
    create_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'export-test-skill',
            'description': 'A skill for export testing',
            'content': '# Export Test\n\n## Steps\n1. Do something',
            'license': 'Apache-2.0',
            'tags': ['export'],
            'importance': 7,
        },
    })
    skill_id = create_result.data["id"]

    export_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'export_skill',
        'arguments': {'skill_id': skill_id},
    })
    # export_skill returns a plain string, so access via content[0].text
    exported = export_result.content[0].text
    assert '---' in exported
    assert 'name: export-test-skill' in exported
    assert 'description: A skill for export testing' in exported
    assert '# Export Test' in exported


@pytest.mark.asyncio
async def test_import_export_roundtrip(mcp_client):
    """Test that importing and exporting preserves key fields"""
    original_md = """---
name: roundtrip-skill
description: Roundtrip test skill
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
    import_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'import_skill',
        'arguments': {
            'skill_md_content': original_md,
            'importance': 9,
        },
    })
    skill_id = import_result.data["id"]

    export_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'export_skill',
        'arguments': {'skill_id': skill_id},
    })
    # export_skill returns a plain string, so access via content[0].text
    exported = export_result.content[0].text
    assert 'name: roundtrip-skill' in exported
    assert 'description: Roundtrip test skill' in exported
    assert 'license: MIT' in exported
    assert '# Roundtrip Skill' in exported


@pytest.mark.asyncio
async def test_create_skill_invalid_name(mcp_client):
    """Test that creating a skill with uppercase name fails validation"""
    try:
        await mcp_client.call_tool('execute_forgetful_tool', {
            'tool_name': 'create_skill',
            'arguments': {
                'name': 'InvalidName',
                'description': 'Should fail validation',
                'content': 'This should not be created',
                'tags': [],
                'importance': 7,
            },
        })
        assert False, 'Expected error for invalid skill name'
    except Exception as e:
        error_msg = str(e).lower()
        assert 'kebab' in error_msg or 'invalid' in error_msg or 'name' in error_msg


@pytest.mark.asyncio
async def test_link_skill_to_memory(mcp_client):
    """Test linking a skill to a memory"""
    # Create a skill
    skill_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'link-test-skill',
            'description': 'Skill for link testing',
            'content': 'Link test content',
            'tags': ['link-test'],
            'importance': 7,
        },
    })
    skill_id = skill_result.data["id"]

    # Create a memory
    memory_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory',
        'arguments': {
            'title': 'Link Test Memory',
            'content': 'Memory for skill link testing',
            'context': 'Testing skill-memory linking',
            'keywords': ['link', 'test'],
            'tags': ['link-test'],
            'importance': 7,
        },
    })
    memory_id = memory_result.data["id"]

    # Link skill to memory
    link_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_skill_to_memory',
        'arguments': {
            'skill_id': skill_id,
            'memory_id': memory_id,
        },
    })
    assert link_result.data is not None
    assert link_result.data["linked"] is True
    assert link_result.data["skill_id"] == skill_id
    assert link_result.data["memory_id"] == memory_id


@pytest.mark.asyncio
async def test_unlink_skill_from_memory(mcp_client):
    """Test unlinking a skill from a memory"""
    # Create a skill
    skill_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_skill',
        'arguments': {
            'name': 'unlink-test-skill',
            'description': 'Skill for unlink testing',
            'content': 'Unlink test content',
            'tags': ['unlink-test'],
            'importance': 7,
        },
    })
    skill_id = skill_result.data["id"]

    # Create a memory
    memory_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'create_memory',
        'arguments': {
            'title': 'Unlink Test Memory',
            'content': 'Memory for skill unlink testing',
            'context': 'Testing skill-memory unlinking',
            'keywords': ['unlink', 'test'],
            'tags': ['unlink-test'],
            'importance': 7,
        },
    })
    memory_id = memory_result.data["id"]

    # Link skill to memory
    await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'link_skill_to_memory',
        'arguments': {
            'skill_id': skill_id,
            'memory_id': memory_id,
        },
    })

    # Unlink skill from memory
    unlink_result = await mcp_client.call_tool('execute_forgetful_tool', {
        'tool_name': 'unlink_skill_from_memory',
        'arguments': {
            'skill_id': skill_id,
            'memory_id': memory_id,
        },
    })
    assert unlink_result.data is not None
    assert unlink_result.data["unlinked"] is True
    assert unlink_result.data["skill_id"] == skill_id
    assert unlink_result.data["memory_id"] == memory_id
