"""Tests for dynamic meta-tool docstring generation.

The discover_forgetful_tools and execute_forgetful_tool docstrings are built
dynamically at startup based on feature flags. These tests verify that
feature-flagged tool sections only appear when their flags are enabled.
"""

from unittest.mock import patch

from app.routes.mcp.meta_tools import (
    _build_category_list,
    _build_discover_docstring,
    _build_execute_docstring,
    _build_tool_categories_line,
)


class TestBuildCategoryList:
    """Verify the category filter list reflects enabled features."""

    def test_core_categories_always_present(self):
        """Core categories appear regardless of feature flags."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            result = _build_category_list()

        for cat in ["user", "memory", "project", "code_artifact", "document", "entity", "linking"]:
            assert cat in result

    def test_skill_category_when_enabled(self):
        """Skill category appears only when SKILLS_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            result = _build_category_list()

        assert "skill" in result

    def test_skill_category_absent_when_disabled(self):
        """Skill category absent when SKILLS_ENABLED=False."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            result = _build_category_list()

        assert "skill" not in result

    def test_plan_task_categories_when_enabled(self):
        """Plan and task categories appear when PLANNING_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = True

            result = _build_category_list()

        assert "plan" in result
        assert "task" in result

    def test_plan_task_categories_absent_when_disabled(self):
        """Plan and task categories absent when PLANNING_ENABLED=False."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            result = _build_category_list()

        assert "plan" not in result
        assert "task" not in result

    def test_file_category_when_enabled(self):
        """File category appears when FILES_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = True
            mock_settings.PLANNING_ENABLED = False

            result = _build_category_list()

        assert "file" in result

    def test_all_features_enabled(self):
        """All categories present when all features enabled."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = True
            mock_settings.PLANNING_ENABLED = True

            result = _build_category_list()

        for cat in ["user", "memory", "project", "code_artifact", "document",
                     "entity", "linking", "skill", "file", "plan", "task"]:
            assert cat in result


class TestBuildToolCategoriesLine:
    """Verify the pipe-separated categories line in execute_forgetful_tool."""

    def test_core_categories_only(self):
        """Only core categories when no features enabled."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            result = _build_tool_categories_line()

        assert "skill" not in result
        assert "plan" not in result
        assert "task" not in result
        assert "file" not in result
        assert "memory" in result

    def test_all_categories_when_all_enabled(self):
        """All categories in pipe line when all features enabled."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = True
            mock_settings.PLANNING_ENABLED = True

            result = _build_tool_categories_line()

        assert "skill" in result
        assert "file" in result
        assert "plan" in result
        assert "task" in result


class TestDiscoverDocstring:
    """Verify discover_forgetful_tools docstring includes/excludes sections by flag."""

    def test_no_optional_sections_when_all_disabled(self):
        """Feature-flagged sections absent when all flags are False."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_discover_docstring()

        # Core sections present
        assert "**User Tools**" in doc
        assert "**Memory Tools**" in doc
        assert "**Entity Tools**" in doc

        # Feature-flagged sections absent
        assert "**Skill Tools**" not in doc
        assert "**File Tools**" not in doc
        assert "**Plan Tools**" not in doc
        assert "**Task Tools**" not in doc

    def test_skill_section_when_enabled(self):
        """Skill tools section included when SKILLS_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_discover_docstring()

        assert "**Skill Tools**" in doc
        assert "create_skill" in doc
        assert "search_skills" in doc

        # Others still absent
        assert "**Plan Tools**" not in doc
        assert "**Task Tools**" not in doc

    def test_planning_sections_when_enabled(self):
        """Plan and Task tools sections included when PLANNING_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = True

            doc = _build_discover_docstring()

        assert "**Plan Tools**" in doc
        assert "create_plan" in doc
        assert "list_plans" in doc
        assert "**Task Tools**" in doc
        assert "create_task" in doc
        assert "claim_task" in doc
        assert "transition_task" in doc

    def test_file_section_when_enabled(self):
        """File tools section included when FILES_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = True
            mock_settings.PLANNING_ENABLED = False

            doc = _build_discover_docstring()

        assert "**File Tools**" in doc
        assert "create_file" in doc

    def test_category_arg_reflects_flags(self):
        """The Args category list in the docstring includes enabled categories."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = True

            doc = _build_discover_docstring()

        # Should appear in the category filter arg description
        assert "skill" in doc
        assert "plan" in doc
        assert "task" in doc

    def test_workflow_section_always_present(self):
        """The workflow section is always appended."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_discover_docstring()

        assert "## Workflow" in doc


class TestExecuteDocstring:
    """Verify execute_forgetful_tool docstring includes/excludes sections by flag."""

    def test_no_optional_sections_when_all_disabled(self):
        """Feature-flagged example sections absent when all flags are False."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_execute_docstring()

        # Core examples present
        assert "**Memory Operations:**" in doc
        assert "**Project Organization:**" in doc

        # Feature-flagged examples absent
        assert "**Skills (procedural knowledge):**" not in doc
        assert "**Files (binary content):**" not in doc
        assert "**Plans (goal tracking):**" not in doc
        assert "**Tasks (work items within plans):**" not in doc

    def test_skill_examples_when_enabled(self):
        """Skill examples included when SKILLS_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_execute_docstring()

        assert "**Skills (procedural knowledge):**" in doc
        assert 'execute_forgetful_tool("create_skill"' in doc

    def test_planning_examples_when_enabled(self):
        """Plan and Task examples included when PLANNING_ENABLED=True."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = True

            doc = _build_execute_docstring()

        assert "**Plans (goal tracking):**" in doc
        assert 'execute_forgetful_tool("create_plan"' in doc
        assert "**Tasks (work items within plans):**" in doc
        assert 'execute_forgetful_tool("create_task"' in doc
        assert 'execute_forgetful_tool("transition_task"' in doc

    def test_tool_categories_line_reflects_flags(self):
        """The Tool Categories line includes enabled feature categories."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = True
            mock_settings.FILES_ENABLED = True
            mock_settings.PLANNING_ENABLED = True

            doc = _build_execute_docstring()

        # The tool categories line should contain all categories
        assert "## Tool Categories" in doc
        assert "skill" in doc
        assert "file" in doc
        assert "plan" in doc
        assert "task" in doc

    def test_linking_section_always_present(self):
        """The linking best practices section is always appended."""
        with patch("app.routes.mcp.meta_tools.settings") as mock_settings:
            mock_settings.SKILLS_ENABLED = False
            mock_settings.FILES_ENABLED = False
            mock_settings.PLANNING_ENABLED = False

            doc = _build_execute_docstring()

        assert "## Linking Best Practices" in doc
