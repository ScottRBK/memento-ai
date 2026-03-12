"""
E2E tests verifying feature flags correctly hide tools and routes when disabled.

Uses the FEATURE_FLAGS registry from conftest — adding a new feature flag there
automatically generates tests here.
"""

import pytest
from fastmcp.exceptions import ToolError

# conftest.py symbols are importable via the conftest module that pytest injects
from conftest import FEATURE_FLAGS, build_sqlite_app


# ============================================================================
# Fixtures: one app per feature flag, with that feature disabled
# ============================================================================

@pytest.fixture(params=list(FEATURE_FLAGS.keys()), ids=[f"{k}-disabled" for k in FEATURE_FLAGS])
async def disabled_feature_client(request, embedding_adapter, reranker_adapter):
    """
    Parameterized fixture that yields (mcp_client, app, feature_name) tuples.

    For each feature flag in FEATURE_FLAGS, creates an app with that feature
    disabled (all OTHER features remain enabled).
    """
    from fastmcp import Client

    disabled_feature = request.param
    all_features = set(FEATURE_FLAGS.keys())
    enabled = all_features - {disabled_feature}

    async for app in build_sqlite_app(embedding_adapter, reranker_adapter, enabled_features=enabled):
        async with Client(app) as client:
            yield client, app, disabled_feature


# ============================================================================
# Tests: auto-generated for each feature flag
# ============================================================================

@pytest.mark.asyncio
async def test_disabled_feature_categories_hidden(disabled_feature_client):
    """When a feature is disabled, its tool categories should not appear."""
    client, app, feature_name = disabled_feature_client
    flag_def = FEATURE_FLAGS[feature_name]

    result = await client.call_tool("discover_forgetful_tools", {})
    categories = result.data["categories_available"]

    for category in flag_def.categories:
        assert category not in categories, (
            f"Category '{category}' should be hidden when '{feature_name}' is disabled"
        )


@pytest.mark.asyncio
async def test_disabled_feature_tools_not_executable(disabled_feature_client):
    """When a feature is disabled, its tools should not be executable."""
    client, app, feature_name = disabled_feature_client
    flag_def = FEATURE_FLAGS[feature_name]

    for tool_name in flag_def.sample_tools:
        with pytest.raises((ToolError, Exception)) as exc_info:
            await client.call_tool(
                "execute_forgetful_tool",
                {"tool_name": tool_name, "arguments": {}},
            )
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg, (
            f"Tool '{tool_name}' should raise 'not found' when '{feature_name}' is disabled, "
            f"got: {error_msg}"
        )


@pytest.mark.asyncio
async def test_disabled_feature_tools_not_in_how_to_use(disabled_feature_client):
    """When a feature is disabled, how_to_use should reject its tools."""
    client, app, feature_name = disabled_feature_client
    flag_def = FEATURE_FLAGS[feature_name]

    for tool_name in flag_def.sample_tools[:1]:  # Just check one to keep fast
        with pytest.raises((ToolError, Exception)) as exc_info:
            await client.call_tool(
                "how_to_use_forgetful_tool",
                {"tool_name": tool_name},
            )
        assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_disabled_feature_core_tools_still_work(disabled_feature_client):
    """Core tools should still function when an optional feature is disabled."""
    client, app, _ = disabled_feature_client

    # Core categories always present
    result = await client.call_tool("discover_forgetful_tools", {})
    categories = result.data["categories_available"]
    for core_cat in ["user", "memory", "project"]:
        assert core_cat in categories, f"Core category '{core_cat}' should always be present"

    # Can still execute a core tool
    user_result = await client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_current_user", "arguments": {}},
    )
    assert user_result.data is not None


@pytest.mark.asyncio
async def test_disabled_feature_routes_404(disabled_feature_client):
    """When a feature is disabled, its REST routes should 404."""
    client, app, feature_name = disabled_feature_client
    flag_def = FEATURE_FLAGS[feature_name]

    if not flag_def.route_prefixes:
        pytest.skip(f"No route prefixes defined for '{feature_name}'")

    from httpx import AsyncClient, ASGITransport

    asgi_app = app.http_app()
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        for prefix in flag_def.route_prefixes:
            response = await http.get(prefix)
            assert response.status_code == 404 or response.status_code == 405, (
                f"Route '{prefix}' should 404/405 when '{feature_name}' is disabled, "
                f"got {response.status_code}"
            )
