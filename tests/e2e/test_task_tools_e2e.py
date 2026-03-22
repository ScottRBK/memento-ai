"""E2E tests for task MCP tools with PostgreSQL backend.

Mirrors tests/e2e_sqlite/test_task_tools_sqlite.py but runs against real Postgres
to catch type mismatches (e.g. UUID vs str) that SQLite doesn't surface.
"""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio(loop_scope="session"),
]


# ---- Helpers ----

async def _create_project(mcp_client, name="task-test-project"):
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_project",
            "arguments": {
                "name": name,
                "description": f"Project for task tests: {name}",
                "project_type": "development",
            },
        },
    )
    return result.data["id"]


async def _create_active_plan(mcp_client, project_id, title="Test plan"):
    """Create a plan and activate it (tasks can only be added to draft/active plans)."""
    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_plan",
            "arguments": {
                "project_id": project_id,
                "title": title,
            },
        },
    )
    plan_id = result.data["id"]
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_plan",
            "arguments": {"plan_id": plan_id, "status": "active"},
        },
    )
    return plan_id


# ---- Task CRUD ----

async def test_create_task_e2e(mcp_client):
    """Test creating a task with all fields"""
    project_id = await _create_project(mcp_client, "pg-task-create-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {
                "plan_id": plan_id,
                "title": "Implement login",
                "description": "Build login form with OAuth",
                "priority": "P1",
            },
        },
    )
    assert result.data is not None
    assert result.data["id"] is not None
    assert result.data["title"] == "Implement login"
    assert result.data["description"] == "Build login form with OAuth"
    assert result.data["state"] == "todo"
    assert result.data["priority"] == "P1"
    assert result.data["version"] == 1
    assert result.data["plan_id"] == plan_id


async def test_get_task_e2e(mcp_client):
    """Test creating then retrieving a task"""
    project_id = await _create_project(mcp_client, "pg-task-get-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {
                "plan_id": plan_id,
                "title": "Get task test",
            },
        },
    )
    task_id = create_result.data["id"]

    get_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_task", "arguments": {"task_id": task_id}},
    )
    assert get_result.data["id"] == task_id
    assert get_result.data["title"] == "Get task test"
    assert "criteria" in get_result.data
    assert "dependency_ids" in get_result.data


async def test_query_tasks_e2e(mcp_client):
    """Test querying tasks with filters"""
    project_id = await _create_project(mcp_client, "pg-task-query-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    for i in range(3):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "create_task",
                "arguments": {
                    "plan_id": plan_id,
                    "title": f"Query task {i}",
                    "priority": "P1" if i == 0 else "P2",
                },
            },
        )

    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "query_tasks", "arguments": {"plan_id": plan_id}},
    )
    assert result.data["total_count"] >= 3

    p1_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "query_tasks", "arguments": {"plan_id": plan_id, "priority": "P1"}},
    )
    for t in p1_result.data["tasks"]:
        assert t["priority"] == "P1"


async def test_update_task_e2e(mcp_client):
    """Test updating task metadata"""
    project_id = await _create_project(mcp_client, "pg-task-update-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {
                "plan_id": plan_id,
                "title": "Original task title",
                "priority": "P2",
            },
        },
    )
    task_id = create_result.data["id"]

    update_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "update_task",
            "arguments": {
                "task_id": task_id,
                "title": "Updated task title",
                "priority": "P0",
            },
        },
    )
    assert update_result.data["title"] == "Updated task title"
    assert update_result.data["priority"] == "P0"


# ---- State Machine ----

async def test_transition_task_lifecycle_e2e(mcp_client):
    """Test full task lifecycle: todo -> doing -> done"""
    project_id = await _create_project(mcp_client, "pg-task-lifecycle-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Lifecycle task"},
        },
    )
    task_id = create_result.data["id"]
    version = create_result.data["version"]

    # TODO -> doing
    doing_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "transition_task",
            "arguments": {
                "task_id": task_id,
                "state": "doing",
                "version": version,
            },
        },
    )
    assert doing_result.data["state"] == "doing"
    version = doing_result.data["version"]

    # doing -> done
    done_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "transition_task",
            "arguments": {
                "task_id": task_id,
                "state": "done",
                "version": version,
            },
        },
    )
    assert done_result.data["state"] == "done"


async def test_transition_task_invalid_e2e(mcp_client):
    """Test that invalid state transitions are rejected"""
    project_id = await _create_project(mcp_client, "pg-task-invalid-trans-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Invalid transition task"},
        },
    )
    task_id = create_result.data["id"]
    version = create_result.data["version"]

    # TODO -> done is invalid (must go through doing)
    with pytest.raises((ToolError, Exception)) as exc_info:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "transition_task",
                "arguments": {
                    "task_id": task_id,
                    "state": "done",
                    "version": version,
                },
            },
        )
    error_msg = str(exc_info.value).lower()
    assert "transition" in error_msg or "invalid" in error_msg


# ---- Claim Task ----

async def test_claim_task_e2e(mcp_client):
    """Test claiming a task sets assigned_agent and state=doing"""
    project_id = await _create_project(mcp_client, "pg-task-claim-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Claimable task"},
        },
    )
    task_id = create_result.data["id"]
    version = create_result.data["version"]

    claim_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "claim_task",
            "arguments": {
                "task_id": task_id,
                "agent_id": "agent-alpha",
                "version": version,
            },
        },
    )
    assert claim_result.data["state"] == "doing"
    assert claim_result.data["assigned_agent"] == "agent-alpha"
    assert claim_result.data["version"] == version + 1


async def test_claim_task_version_conflict_e2e(mcp_client):
    """Test that claiming with stale version fails"""
    project_id = await _create_project(mcp_client, "pg-task-conflict-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Conflict task"},
        },
    )
    task_id = create_result.data["id"]
    version = create_result.data["version"]

    # First claim succeeds
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "claim_task",
            "arguments": {
                "task_id": task_id,
                "agent_id": "agent-alpha",
                "version": version,
            },
        },
    )

    # Second claim with stale version fails
    with pytest.raises((ToolError, Exception)) as exc_info:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "claim_task",
                "arguments": {
                    "task_id": task_id,
                    "agent_id": "agent-beta",
                    "version": version,  # stale!
                },
            },
        )
    error_msg = str(exc_info.value).lower()
    assert "conflict" in error_msg or "version" in error_msg or "transition" in error_msg


# ---- Criteria ----

async def test_criteria_lifecycle_e2e(mcp_client):
    """Test adding, verifying, and deleting criteria"""
    project_id = await _create_project(mcp_client, "pg-task-criteria-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Task with criteria"},
        },
    )
    task_id = create_result.data["id"]

    # Add criterion
    criterion_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "add_criterion",
            "arguments": {
                "task_id": task_id,
                "description": "Tests pass in CI",
            },
        },
    )
    assert criterion_result.data["description"] == "Tests pass in CI"
    assert criterion_result.data["met"] is False
    criterion_id = criterion_result.data["id"]

    # Verify criterion
    verify_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "verify_criterion",
            "arguments": {
                "criterion_id": criterion_id,
                "met": True,
            },
        },
    )
    assert verify_result.data["met"] is True
    assert verify_result.data["met_at"] is not None

    # Delete criterion
    delete_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "delete_criterion",
            "arguments": {"criterion_id": criterion_id},
        },
    )
    assert delete_result.data["success"] is True


async def test_done_requires_criteria_met_e2e(mcp_client):
    """Test that transitioning to done requires all criteria to be met"""
    project_id = await _create_project(mcp_client, "pg-task-criteria-gate-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    create_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {"plan_id": plan_id, "title": "Criteria gated task"},
        },
    )
    task_id = create_result.data["id"]
    version = create_result.data["version"]

    # Add unmet criterion
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "add_criterion",
            "arguments": {
                "task_id": task_id,
                "description": "Must be verified first",
            },
        },
    )

    # Transition to doing
    doing_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "transition_task",
            "arguments": {"task_id": task_id, "state": "doing", "version": version},
        },
    )
    version = doing_result.data["version"]

    # Attempt to transition to done — should fail (unmet criterion)
    with pytest.raises((ToolError, Exception)) as exc_info:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "transition_task",
                "arguments": {"task_id": task_id, "state": "done", "version": version},
            },
        )
    error_msg = str(exc_info.value).lower()
    assert "criteria" in error_msg or "met" in error_msg or "transition" in error_msg


# ---- Dependencies ----

async def test_dependency_chain_e2e(mcp_client):
    """Test dependency chain: A depends on B depends on C. Complete C -> B -> A."""
    project_id = await _create_project(mcp_client, "pg-task-dep-chain-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    # Create tasks C, B, A
    c_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Task C"}},
    )
    task_c_id = c_result.data["id"]

    b_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Task B"}},
    )
    task_b_id = b_result.data["id"]

    a_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Task A"}},
    )
    task_a_id = a_result.data["id"]

    # Add dependencies: A -> B, B -> C
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "add_dependency",
            "arguments": {"task_id": task_a_id, "depends_on_task_id": task_b_id},
        },
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "add_dependency",
            "arguments": {"task_id": task_b_id, "depends_on_task_id": task_c_id},
        },
    )

    # Verify dependencies show up in get_task
    a_data = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_task", "arguments": {"task_id": task_a_id}},
    )
    assert task_b_id in a_data.data["dependency_ids"]

    # A can't start because B isn't done
    with pytest.raises((ToolError, Exception)):
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {
                "tool_name": "transition_task",
                "arguments": {"task_id": task_a_id, "state": "doing", "version": 1},
            },
        )

    # Complete C: todo -> doing -> done
    c_doing = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_c_id, "state": "doing", "version": 1}},
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_c_id, "state": "done", "version": c_doing.data["version"]}},
    )

    # Now B can start
    b_doing = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_b_id, "state": "doing", "version": 1}},
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_b_id, "state": "done", "version": b_doing.data["version"]}},
    )

    # Now A can start and complete
    a_doing = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_a_id, "state": "doing", "version": 1}},
    )
    a_done = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "transition_task", "arguments": {"task_id": task_a_id, "state": "done", "version": a_doing.data["version"]}},
    )
    assert a_done.data["state"] == "done"


async def test_cyclic_dependency_rejected_e2e(mcp_client):
    """Test that circular dependencies are rejected"""
    project_id = await _create_project(mcp_client, "pg-task-cycle-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    a_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Cycle A"}},
    )
    b_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Cycle B"}},
    )
    c_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Cycle C"}},
    )

    task_a_id = a_result.data["id"]
    task_b_id = b_result.data["id"]
    task_c_id = c_result.data["id"]

    # A -> B -> C (valid)
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "add_dependency", "arguments": {"task_id": task_a_id, "depends_on_task_id": task_b_id}},
    )
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "add_dependency", "arguments": {"task_id": task_b_id, "depends_on_task_id": task_c_id}},
    )

    # C -> A would create cycle
    with pytest.raises((ToolError, Exception)) as exc_info:
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "add_dependency", "arguments": {"task_id": task_c_id, "depends_on_task_id": task_a_id}},
        )
    error_msg = str(exc_info.value).lower()
    assert "cycle" in error_msg or "cyclic" in error_msg


async def test_remove_dependency_e2e(mcp_client):
    """Test removing a dependency"""
    project_id = await _create_project(mcp_client, "pg-task-remove-dep-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    a_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Dep remove A"}},
    )
    b_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Dep remove B"}},
    )
    task_a_id = a_result.data["id"]
    task_b_id = b_result.data["id"]

    # Add then remove
    await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "add_dependency", "arguments": {"task_id": task_a_id, "depends_on_task_id": task_b_id}},
    )
    remove_result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "remove_dependency", "arguments": {"task_id": task_a_id, "depends_on_task_id": task_b_id}},
    )
    assert remove_result.data["success"] is True

    # Verify dependency is gone
    a_data = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_task", "arguments": {"task_id": task_a_id}},
    )
    assert task_b_id not in a_data.data["dependency_ids"]


# ---- Plan Auto-Completion ----

async def test_plan_auto_completes_when_all_tasks_done_e2e(mcp_client):
    """Test that plan auto-transitions to completed when all tasks are done"""
    project_id = await _create_project(mcp_client, "pg-task-auto-complete-proj")
    plan_id = await _create_active_plan(mcp_client, project_id, "Auto-complete plan")

    # Create two tasks
    t1 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Auto task 1"}},
    )
    t2 = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "create_task", "arguments": {"plan_id": plan_id, "title": "Auto task 2"}},
    )

    # Complete both tasks
    for t in [t1, t2]:
        tid = t.data["id"]
        doing = await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "transition_task", "arguments": {"task_id": tid, "state": "doing", "version": 1}},
        )
        await mcp_client.call_tool(
            "execute_forgetful_tool",
            {"tool_name": "transition_task", "arguments": {"task_id": tid, "state": "done", "version": doing.data["version"]}},
        )

    # Verify plan auto-completed
    plan_data = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {"tool_name": "get_plan", "arguments": {"plan_id": plan_id}},
    )
    assert plan_data.data["status"] == "completed"


# ---- Create Task with Inline Criteria ----

async def test_create_task_with_inline_criteria_e2e(mcp_client):
    """Test creating a task with criteria specified inline"""
    project_id = await _create_project(mcp_client, "pg-task-inline-crit-proj")
    plan_id = await _create_active_plan(mcp_client, project_id)

    result = await mcp_client.call_tool(
        "execute_forgetful_tool",
        {
            "tool_name": "create_task",
            "arguments": {
                "plan_id": plan_id,
                "title": "Task with inline criteria",
                "criteria": [
                    {"description": "Unit tests pass"},
                    {"description": "Code reviewed"},
                ],
            },
        },
    )
    assert result.data is not None
    assert len(result.data["criteria"]) == 2
    descriptions = [c["description"] for c in result.data["criteria"]]
    assert "Unit tests pass" in descriptions
    assert "Code reviewed" in descriptions


# ---- Discover Task Tools ----

async def test_task_discover_tools_e2e(mcp_client):
    """Test that task tools appear in discover_forgetful_tools"""
    result = await mcp_client.call_tool(
        "discover_forgetful_tools",
        {"category": "task"},
    )
    assert result.data is not None
    assert "task" in result.data["tools_by_category"]
    task_tools = result.data["tools_by_category"]["task"]
    tool_names = [t["name"] for t in task_tools]
    expected = [
        "create_task", "update_task", "get_task", "query_tasks",
        "claim_task", "transition_task",
        "add_criterion", "verify_criterion", "delete_criterion",
        "add_dependency", "remove_dependency",
    ]
    for name in expected:
        assert name in tool_names, f"Missing tool: {name}"
