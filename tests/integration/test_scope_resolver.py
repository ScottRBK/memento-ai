"""
Integration tests for the ScopeResolver module.

Tests scope parsing, validation, resolution, and the effective scopes logic.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.routes.mcp.scope_resolver import (
    parse_scopes,
    resolve_permitted_tools,
    get_required_scope,
    get_effective_scopes,
    CATEGORY_TO_SCOPE,
    VALID_ACTIONS,
    VALID_CATEGORIES,
)
from app.routes.mcp.tool_registry import ToolRegistry
from app.models.tool_registry_models import ToolCategory, ToolParameter


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def registry_with_tools():
    """Create a registry with a mix of read and write tools across categories."""
    registry = ToolRegistry()
    params = [ToolParameter(name="ctx", type="Context", description="ctx", required=True)]

    # User tools
    async def noop(**kwargs):
        return {}

    registry.register(
        name="get_current_user", category=ToolCategory.USER,
        description="Read user", parameters=params, returns="User",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="update_user_notes", category=ToolCategory.USER,
        description="Update notes", parameters=params, returns="User",
        implementation=noop, mutates=True,
    )

    # Memory tools
    registry.register(
        name="query_memory", category=ToolCategory.MEMORY,
        description="Search memories", parameters=params, returns="Results",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="get_memory", category=ToolCategory.MEMORY,
        description="Get memory", parameters=params, returns="Memory",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="create_memory", category=ToolCategory.MEMORY,
        description="Create memory", parameters=params, returns="Memory",
        implementation=noop, mutates=True,
    )
    registry.register(
        name="update_memory", category=ToolCategory.MEMORY,
        description="Update memory", parameters=params, returns="Memory",
        implementation=noop, mutates=True,
    )

    # Project tools
    registry.register(
        name="list_projects", category=ToolCategory.PROJECT,
        description="List projects", parameters=params, returns="Projects",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="create_project", category=ToolCategory.PROJECT,
        description="Create project", parameters=params, returns="Project",
        implementation=noop, mutates=True,
    )

    # Entity tools
    registry.register(
        name="get_entity", category=ToolCategory.ENTITY,
        description="Get entity", parameters=params, returns="Entity",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="create_entity", category=ToolCategory.ENTITY,
        description="Create entity", parameters=params, returns="Entity",
        implementation=noop, mutates=True,
    )

    # Document tools
    registry.register(
        name="get_document", category=ToolCategory.DOCUMENT,
        description="Get doc", parameters=params, returns="Doc",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="create_document", category=ToolCategory.DOCUMENT,
        description="Create doc", parameters=params, returns="Doc",
        implementation=noop, mutates=True,
    )

    # Code artifact tools
    registry.register(
        name="get_code_artifact", category=ToolCategory.CODE_ARTIFACT,
        description="Get artifact", parameters=params, returns="Artifact",
        implementation=noop, mutates=False,
    )
    registry.register(
        name="create_code_artifact", category=ToolCategory.CODE_ARTIFACT,
        description="Create artifact", parameters=params, returns="Artifact",
        implementation=noop, mutates=True,
    )

    return registry


# ============================================================================
# parse_scopes tests
# ============================================================================

class TestParseScopes:
    def test_wildcard(self):
        result = parse_scopes("*")
        assert result == frozenset({"*"})

    def test_single_read(self):
        result = parse_scopes("read")
        assert result == frozenset({"read"})

    def test_single_write(self):
        result = parse_scopes("write")
        assert result == frozenset({"write"})

    def test_multiple_scopes(self):
        result = parse_scopes("read,write:memories")
        assert result == frozenset({"read", "write:memories"})

    def test_whitespace_handling(self):
        result = parse_scopes("  read , write:memories  ")
        assert result == frozenset({"read", "write:memories"})

    def test_all_valid_categories(self):
        for cat in VALID_CATEGORIES:
            result = parse_scopes(f"read:{cat}")
            assert f"read:{cat}" in result

    def test_all_valid_actions(self):
        for action in VALID_ACTIONS:
            result = parse_scopes(f"{action}:memories")
            assert f"{action}:memories" in result

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_scopes("")

    def test_invalid_whitespace_only(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_scopes("   ")

    def test_invalid_action(self):
        with pytest.raises(ValueError, match="Invalid scope action"):
            parse_scopes("delete:memories")

    def test_invalid_category(self):
        with pytest.raises(ValueError, match="Invalid scope category"):
            parse_scopes("read:nonexistent")

    def test_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid scope token"):
            parse_scopes("foobar")

    def test_mixed_valid_invalid(self):
        with pytest.raises(ValueError, match="Invalid scope token"):
            parse_scopes("read,foobar")

    def test_combined_scopes(self):
        result = parse_scopes("read:memories,write:entities,read:projects")
        assert result == frozenset({"read:memories", "write:entities", "read:projects"})


# ============================================================================
# resolve_permitted_tools tests
# ============================================================================

class TestResolvePermittedTools:
    def test_wildcard_returns_all(self, registry_with_tools):
        scopes = frozenset({"*"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        all_tools = {m.name for m in registry_with_tools.list_all_tools()}
        assert permitted == all_tools

    def test_read_returns_non_mutating_only(self, registry_with_tools):
        scopes = frozenset({"read"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert "query_memory" in permitted
        assert "get_memory" in permitted
        assert "get_current_user" in permitted
        assert "list_projects" in permitted
        assert "create_memory" not in permitted
        assert "update_memory" not in permitted
        assert "create_project" not in permitted

    def test_write_returns_mutating_only(self, registry_with_tools):
        scopes = frozenset({"write"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert "create_memory" in permitted
        assert "update_memory" in permitted
        assert "update_user_notes" in permitted
        assert "query_memory" not in permitted
        assert "get_memory" not in permitted

    def test_read_memories_only(self, registry_with_tools):
        scopes = frozenset({"read:memories"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert permitted == {"query_memory", "get_memory"}

    def test_write_memories_only(self, registry_with_tools):
        scopes = frozenset({"write:memories"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert permitted == {"create_memory", "update_memory"}

    def test_combined_read_and_write_memories(self, registry_with_tools):
        scopes = frozenset({"read", "write:memories"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        # All reads + memory writes
        assert "query_memory" in permitted
        assert "get_memory" in permitted
        assert "get_current_user" in permitted
        assert "list_projects" in permitted
        assert "create_memory" in permitted
        assert "update_memory" in permitted
        # No non-memory writes
        assert "create_project" not in permitted
        assert "update_user_notes" not in permitted

    def test_read_entities(self, registry_with_tools):
        scopes = frozenset({"read:entities"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert "get_entity" in permitted
        assert "create_entity" not in permitted

    def test_empty_result_for_unused_category(self, registry_with_tools):
        # All tools are accounted for, but let's test a scope combination
        # that results in an empty set
        scopes = frozenset({"write:users"})
        permitted = resolve_permitted_tools(scopes, registry_with_tools)
        assert "update_user_notes" in permitted
        assert len(permitted) == 1


# ============================================================================
# get_required_scope tests
# ============================================================================

class TestGetRequiredScope:
    def test_read_tool(self, registry_with_tools):
        scope = get_required_scope("query_memory", registry_with_tools)
        assert scope == "read:memories"

    def test_write_tool(self, registry_with_tools):
        scope = get_required_scope("create_memory", registry_with_tools)
        assert scope == "write:memories"

    def test_user_read_tool(self, registry_with_tools):
        scope = get_required_scope("get_current_user", registry_with_tools)
        assert scope == "read:users"

    def test_user_write_tool(self, registry_with_tools):
        scope = get_required_scope("update_user_notes", registry_with_tools)
        assert scope == "write:users"

    def test_nonexistent_tool(self, registry_with_tools):
        scope = get_required_scope("nonexistent", registry_with_tools)
        assert scope == "unknown"


# ============================================================================
# get_effective_scopes tests
# ============================================================================

class TestGetEffectiveScopes:
    def _make_ctx(self, instance_permitted=None, instance_scopes=None, registry=None):
        """Create a mock Context with expected attributes."""
        ctx = MagicMock()
        ctx.fastmcp._instance_permitted_tools = instance_permitted
        ctx.fastmcp._instance_scopes = instance_scopes or frozenset({"*"})
        ctx.fastmcp.registry = registry or MagicMock()
        if registry:
            ctx.fastmcp.registry = registry
        return ctx

    @patch("app.routes.mcp.scope_resolver._extract_token_scopes", return_value=None)
    def test_instance_only_fallback(self, mock_token, registry_with_tools):
        """When no token scopes, fall back to instance scopes."""
        all_tools = {m.name for m in registry_with_tools.list_all_tools()}
        ctx = self._make_ctx(
            instance_permitted=all_tools,
            instance_scopes=frozenset({"*"}),
            registry=registry_with_tools,
        )

        permitted, scopes = get_effective_scopes(ctx)
        assert permitted == all_tools
        assert "*" in scopes

    @patch("app.routes.mcp.scope_resolver._extract_token_scopes", return_value=frozenset({"read"}))
    def test_token_intersection(self, mock_token, registry_with_tools):
        """Token scopes should intersect with instance ceiling."""
        all_tools = {m.name for m in registry_with_tools.list_all_tools()}
        ctx = self._make_ctx(
            instance_permitted=all_tools,
            instance_scopes=frozenset({"*"}),
            registry=registry_with_tools,
        )

        permitted, scopes = get_effective_scopes(ctx)
        # Should only contain read tools
        assert "query_memory" in permitted
        assert "create_memory" not in permitted

    @patch("app.routes.mcp.scope_resolver._extract_token_scopes", return_value=None)
    def test_no_instance_scopes_fallback(self, mock_token, registry_with_tools):
        """When _instance_permitted_tools is not set, allow all (backwards compat)."""
        ctx = self._make_ctx(
            instance_permitted=None,
            registry=registry_with_tools,
        )

        permitted, scopes = get_effective_scopes(ctx)
        all_tools = {m.name for m in registry_with_tools.list_all_tools()}
        assert permitted == all_tools
        assert "*" in scopes

    @patch("app.routes.mcp.scope_resolver._extract_token_scopes", return_value=frozenset({"write:memories"}))
    def test_token_narrows_instance(self, mock_token, registry_with_tools):
        """Token with write:memories should narrow to only memory writes, even with * instance scope."""
        all_tools = {m.name for m in registry_with_tools.list_all_tools()}
        ctx = self._make_ctx(
            instance_permitted=all_tools,
            instance_scopes=frozenset({"*"}),
            registry=registry_with_tools,
        )

        permitted, scopes = get_effective_scopes(ctx)
        assert permitted == {"create_memory", "update_memory"}


# ============================================================================
# CATEGORY_TO_SCOPE mapping tests
# ============================================================================

class TestCategoryMapping:
    def test_all_categories_mapped(self):
        """Every ToolCategory should have a scope mapping."""
        for cat in ToolCategory:
            assert cat.value in CATEGORY_TO_SCOPE, f"Category {cat.value} missing from CATEGORY_TO_SCOPE"

    def test_linking_maps_to_entities(self):
        """Linking category should map to entities scope."""
        assert CATEGORY_TO_SCOPE["linking"] == "entities"
