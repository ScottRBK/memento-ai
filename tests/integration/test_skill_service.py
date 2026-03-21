"""
Integration tests for SkillService with in-memory stubs
"""
import pytest
from uuid import uuid4

from app.models.skill_models import SkillCreate, SkillUpdate
from app.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_skill(test_skill_service):
    user_id = uuid4()

    skill_data = SkillCreate(
        name="pdf-processing",
        description="Extract and summarise PDF documents",
        content="# PDF Processing\n\nUse PyMuPDF to extract text...",
        license="MIT",
        compatibility="Requires Python 3.10+",
        allowed_tools=["Bash(python:*)", "Read"],
        metadata={"author": "scottesh", "version": "1.0.0"},
        tags=["pdf", "extraction"],
        importance=8,
    )

    skill = await test_skill_service.create_skill(user_id, skill_data)

    assert skill.id is not None
    assert skill.name == "pdf-processing"
    assert skill.description == "Extract and summarise PDF documents"
    assert skill.content == "# PDF Processing\n\nUse PyMuPDF to extract text..."
    assert skill.license == "MIT"
    assert skill.compatibility == "Requires Python 3.10+"
    assert skill.allowed_tools == ["Bash(python:*)", "Read"]
    assert skill.metadata == {"author": "scottesh", "version": "1.0.0"}
    assert skill.tags == ["pdf", "extraction"]
    assert skill.importance == 8
    assert skill.created_at is not None
    assert skill.updated_at is not None


@pytest.mark.asyncio
async def test_create_skill_invalid_name(test_skill_service):
    user_id = uuid4()

    # Uppercase letters should be rejected
    with pytest.raises(ValueError):
        SkillCreate(
            name="PDF-Processing",
            description="Extract PDFs",
            content="Some content",
        )

    # Spaces should be rejected
    with pytest.raises(ValueError):
        SkillCreate(
            name="pdf processing",
            description="Extract PDFs",
            content="Some content",
        )

    # Leading hyphens should be rejected
    with pytest.raises(ValueError):
        SkillCreate(
            name="-pdf-processing",
            description="Extract PDFs",
            content="Some content",
        )


@pytest.mark.asyncio
async def test_get_skill(test_skill_service):
    user_id = uuid4()

    skill_data = SkillCreate(
        name="code-review",
        description="Perform code reviews",
        content="# Code Review\n\nReview code for quality...",
        tags=["code"],
    )
    created = await test_skill_service.create_skill(user_id, skill_data)

    retrieved = await test_skill_service.get_skill(user_id, created.id)

    assert retrieved.id == created.id
    assert retrieved.name == "code-review"
    assert retrieved.description == "Perform code reviews"


@pytest.mark.asyncio
async def test_get_skill_not_found(test_skill_service):
    user_id = uuid4()

    with pytest.raises(NotFoundError):
        await test_skill_service.get_skill(user_id, 999)


@pytest.mark.asyncio
async def test_list_skills(test_skill_service):
    user_id = uuid4()

    for i in range(3):
        skill_data = SkillCreate(
            name=f"skill-{i}",
            description=f"Skill number {i}",
            content=f"Content for skill {i}",
            tags=["test"],
        )
        await test_skill_service.create_skill(user_id, skill_data)

    skills = await test_skill_service.list_skills(user_id)

    assert len(skills) == 3


@pytest.mark.asyncio
async def test_list_skills_filter_by_tags(test_skill_service):
    user_id = uuid4()

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="frontend-testing",
            description="Frontend testing skill",
            content="Content",
            tags=["frontend", "testing"],
        ),
    )

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="backend-deploy",
            description="Backend deployment skill",
            content="Content",
            tags=["backend", "deploy"],
        ),
    )

    frontend_skills = await test_skill_service.list_skills(
        user_id, tags=["frontend"]
    )

    assert len(frontend_skills) == 1
    assert "frontend" in frontend_skills[0].tags


@pytest.mark.asyncio
async def test_list_skills_filter_by_importance(test_skill_service):
    user_id = uuid4()

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="low-importance",
            description="Low importance skill",
            content="Content",
            importance=3,
        ),
    )

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="high-importance",
            description="High importance skill",
            content="Content",
            importance=9,
        ),
    )

    high_skills = await test_skill_service.list_skills(
        user_id, importance_threshold=7
    )

    assert len(high_skills) == 1
    assert high_skills[0].importance == 9


@pytest.mark.asyncio
async def test_update_skill(test_skill_service):
    user_id = uuid4()

    skill_data = SkillCreate(
        name="original-skill",
        description="Original description",
        content="Original content",
        tags=["original"],
        importance=5,
    )
    created = await test_skill_service.create_skill(user_id, skill_data)

    update_data = SkillUpdate(
        description="Updated description",
        importance=9,
    )
    updated = await test_skill_service.update_skill(
        user_id, created.id, update_data
    )

    assert updated.description == "Updated description"
    assert updated.importance == 9
    # Unchanged fields preserved
    assert updated.name == "original-skill"
    assert updated.content == "Original content"
    assert updated.tags == ["original"]


@pytest.mark.asyncio
async def test_delete_skill(test_skill_service):
    user_id = uuid4()

    skill_data = SkillCreate(
        name="to-delete",
        description="Will be deleted",
        content="Content",
        tags=[],
    )
    created = await test_skill_service.create_skill(user_id, skill_data)

    success = await test_skill_service.delete_skill(user_id, created.id)
    assert success is True

    with pytest.raises(NotFoundError):
        await test_skill_service.get_skill(user_id, created.id)


@pytest.mark.asyncio
async def test_search_skills(test_skill_service):
    user_id = uuid4()

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="pdf-extract",
            description="Extract text from PDF documents using PyMuPDF",
            content="Content about PDF extraction",
            tags=["pdf"],
        ),
    )

    await test_skill_service.create_skill(
        user_id,
        SkillCreate(
            name="docker-deploy",
            description="Deploy applications using Docker containers",
            content="Content about Docker",
            tags=["docker"],
        ),
    )

    results = await test_skill_service.search_skills(user_id, query="PDF")

    assert len(results) == 1
    assert results[0].name == "pdf-extract"


@pytest.mark.asyncio
async def test_import_skill(test_skill_service):
    user_id = uuid4()

    skill_md = """---
name: git-workflow
description: Standard git workflow for feature branches
license: MIT
compatibility: Requires git 2.30+
allowed-tools:
  - Bash(git:*)
metadata:
  author: scottesh
  version: "1.0.0"
---

# Git Workflow

1. Create a feature branch from main
2. Make commits with conventional messages
3. Open a pull request
4. Squash and merge after approval
"""

    skill = await test_skill_service.import_skill(
        user_id, skill_md, project_id=1, importance=8
    )

    assert skill.name == "git-workflow"
    assert skill.description == "Standard git workflow for feature branches"
    assert skill.license == "MIT"
    assert skill.compatibility == "Requires git 2.30+"
    assert skill.allowed_tools == ["Bash(git:*)"]
    assert skill.metadata == {"author": "scottesh", "version": "1.0.0"}
    assert skill.project_id == 1
    assert skill.importance == 8
    assert "Create a feature branch" in skill.content


@pytest.mark.asyncio
async def test_export_skill(test_skill_service):
    user_id = uuid4()

    skill_data = SkillCreate(
        name="code-review",
        description="Perform thorough code reviews",
        content="# Code Review\n\nReview for correctness, readability, and performance.",
        license="Apache-2.0",
        compatibility="Any environment",
        allowed_tools=["Read", "Grep"],
        metadata={"author": "scottesh"},
        tags=["code"],
    )
    created = await test_skill_service.create_skill(user_id, skill_data)

    exported = await test_skill_service.export_skill(user_id, created.id)

    assert exported.startswith("---\n")
    assert "name: code-review" in exported
    assert "description: Perform thorough code reviews" in exported
    assert "license: Apache-2.0" in exported
    assert "compatibility: Any environment" in exported
    assert "# Code Review" in exported
    assert "Review for correctness, readability, and performance." in exported


@pytest.mark.asyncio
async def test_import_export_roundtrip(test_skill_service):
    user_id = uuid4()

    original_md = """---
name: test-roundtrip
description: A skill to test roundtrip import/export
license: MIT
compatibility: Python 3.10+
metadata:
  author: scottesh
  version: '2.0.0'
allowed-tools:
  - Bash(python:*)
  - Read
  - WebFetch
---

# Test Roundtrip Skill

This skill tests that import and export are inverses.

## Steps

1. Parse the frontmatter
2. Extract the body
3. Reconstruct the output
"""

    # Import
    skill = await test_skill_service.import_skill(user_id, original_md)

    # Export
    exported = await test_skill_service.export_skill(user_id, skill.id)

    # Verify key fields survive the roundtrip
    assert "name: test-roundtrip" in exported
    assert "description: A skill to test roundtrip import/export" in exported
    assert "license: MIT" in exported
    assert "# Test Roundtrip Skill" in exported
    assert "This skill tests that import and export are inverses." in exported
    assert "- Bash(python:*)" in exported
    assert "- Read" in exported
    assert "- WebFetch" in exported
