"""
E2E tests for plan MCP tools with PostgreSQL backend.

Mirrors tests/e2e_sqlite/test_plan_tools_sqlite.py but runs against real Postgres
to catch type mismatches (e.g. UUID vs str) that SQLite doesn't surface.
"""

import pytest
from fastmcp.exceptions import ToolError


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio(loop_scope="session"),
]


# ---- Helper to create a project (plans require a project_id) ----

async def _create_project(mcp_client, name="test-project"):
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": name,
                "description": f"Project for plan tests: {name}",
                "project_type": "development",
            },
        },
    )
    return result.data["id"]


# ---- Plan CRUD ----

async def test_create_plan_e2e(mcp_client):
    """Test creating a plan with all fields"""
    project_id = await _create_project(mcp_client, "pg-plan-create-proj")

    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Implement feature X",
                "goal": "Deliver feature X by end of sprint",
                "context": "Feature X was requested by the team lead",
            },
        },
    )
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["title"] == "Implement feature X"
    assert result.data["goal"] == "Deliver feature X by end of sprint"
    assert result.data["context"] == "Feature X was requested by the team lead"
    assert result.data["status"] == "draft"
    assert result.data["project_id"] == project_id
    assert result.data["created_at"] is not None
    assert result.data["updated_at"] is not None


async def test_get_plan_e2e(mcp_client):
    """Test creating then retrieving a plan"""
    project_id = await _create_project(mcp_client, "pg-plan-get-proj")

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Get plan test",
            },
        },
    )
    plan_id = create_result.data["id"]

    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_plan", "arguments": {"plan_id": plan_id}},
    )
    assert get_result.data is not None
    assert get_result.data["id"] == plan_id
    assert get_result.data["title"] == "Get plan test"


async def test_list_plans_e2e(mcp_client):
    """Test listing plans with project filter"""
    project_id = await _create_project(mcp_client, "pg-plan-list-proj")

    for i in range(3):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_plan",
                "arguments": {
                    "project_id": project_id,
                    "title": f"List plan {i}",
                },
            },
        )

    list_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "list_plans", "arguments": {"project_id": project_id}},
    )
    assert list_result.data is not None
    assert list_result.data["total_count"] >= 3
    titles = [p["title"] for p in list_result.data["plans"]]
    for i in range(3):
        assert f"List plan {i}" in titles


async def test_update_plan_e2e(mcp_client):
    """Test updating a plan (title, goal, status)"""
    project_id = await _create_project(mcp_client, "pg-plan-update-proj")

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Original title",
                "goal": "Original goal",
            },
        },
    )
    plan_id = create_result.data["id"]

    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_plan",
            "arguments": {
                "plan_id": plan_id,
                "title": "Updated title",
                "goal": "Updated goal",
            },
        },
    )
    assert update_result.data["title"] == "Updated title"
    assert update_result.data["goal"] == "Updated goal"


async def test_plan_create_defaults_e2e(mcp_client):
    """Test that plan defaults are applied correctly (status=draft, no goal/context)"""
    project_id = await _create_project(mcp_client, "pg-plan-defaults-proj")

    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Minimal plan",
            },
        },
    )
    assert result.data["status"] == "draft"
    assert result.data["goal"] is None
    assert result.data["context"] is None


# ---- Plan Status Transitions ----

async def test_plan_lifecycle_e2e(mcp_client):
    """Test plan status lifecycle: draft -> active -> completed"""
    project_id = await _create_project(mcp_client, "pg-plan-lifecycle-proj")

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Lifecycle plan",
            },
        },
    )
    plan_id = create_result.data["id"]
    assert create_result.data["status"] == "draft"

    # draft -> active
    active_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_plan",
            "arguments": {"plan_id": plan_id, "status": "active"},
        },
    )
    assert active_result.data["status"] == "active"

    # active -> completed
    completed_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_plan",
            "arguments": {"plan_id": plan_id, "status": "completed"},
        },
    )
    assert completed_result.data["status"] == "completed"


async def test_plan_invalid_status_transition_e2e(mcp_client):
    """Test that invalid status transitions are rejected"""
    project_id = await _create_project(mcp_client, "pg-plan-invalid-trans-proj")

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Invalid transition plan",
            },
        },
    )
    plan_id = create_result.data["id"]

    # draft -> completed is invalid (must go through active)
    with pytest.raises((ToolError, Exception)) as exc_info:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "update_plan",
                "arguments": {"plan_id": plan_id, "status": "completed"},
            },
        )
    assert "transition" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


async def test_list_plans_filter_by_status_e2e(mcp_client):
    """Test filtering plans by status"""
    project_id = await _create_project(mcp_client, "pg-plan-filter-status-proj")

    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Draft plan for filter",
            },
        },
    )

    active_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": "Active plan for filter",
            },
        },
    )
    active_plan_id = active_result.data["id"]
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_plan",
            "arguments": {"plan_id": active_plan_id, "status": "active"},
        },
    )

    list_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "list_plans",
            "arguments": {"project_id": project_id, "status": "active"},
        },
    )
    plans = list_result.data["plans"]
    assert len(plans) >= 1
    for p in plans:
        assert p["status"] == "active"
    titles = [p["title"] for p in plans]
    assert "Active plan for filter" in titles
    assert "Draft plan for filter" not in titles


async def test_plan_discover_tools_e2e(mcp_client):
    """Test that plan tools appear in discover_forgetful_tools"""
    result = await mcp_client.call_tool(
        "discover_forgetful_tools",
        {"category": "plan"},
    )
    assert result.data is not None
    assert "plan" in result.data["tools_by_category"]
    plan_tools = result.data["tools_by_category"]["plan"]
    tool_names = [t["name"] for t in plan_tools]
    assert "create_plan" in tool_names
    assert "get_plan" in tool_names
    assert "list_plans" in tool_names
    assert "update_plan" in tool_names
