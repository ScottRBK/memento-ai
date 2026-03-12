"""
Integration tests for PlanService with in-memory stubs
"""

import pytest
from uuid import uuid4

from app.models.plan_models import PlanCreate, PlanUpdate, PlanStatus


@pytest.mark.asyncio
async def test_create_plan_basic(test_plan_service):
    """Test creating a plan and verifying all returned fields."""
    user_id = uuid4()

    plan_data = PlanCreate(title="My Plan", project_id=1, goal="Build feature X")
    plan = await test_plan_service.create_plan(user_id=user_id, plan_data=plan_data)

    assert plan is not None
    assert plan.id is not None
    assert plan.title == "My Plan"
    assert plan.project_id == 1
    assert plan.goal == "Build feature X"
    assert plan.context is None
    assert plan.status == PlanStatus.DRAFT
    assert plan.user_id == str(user_id)
    assert plan.task_count == 0
    assert plan.created_at is not None
    assert plan.updated_at is not None


@pytest.mark.asyncio
async def test_get_plan(test_plan_service):
    """Test creating then getting a plan; verify returned plan matches."""
    user_id = uuid4()

    plan_data = PlanCreate(title="Retrievable Plan", project_id=2, goal="Test retrieval")
    created = await test_plan_service.create_plan(user_id=user_id, plan_data=plan_data)

    retrieved = await test_plan_service.get_plan(user_id=user_id, plan_id=created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.title == "Retrievable Plan"
    assert retrieved.project_id == 2
    assert retrieved.goal == "Test retrieval"
    assert retrieved.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_list_plans(test_plan_service):
    """Test creating multiple plans and listing all of them."""
    user_id = uuid4()

    for i in range(3):
        plan_data = PlanCreate(title=f"Plan {i}", project_id=1, goal=f"Goal {i}")
        await test_plan_service.create_plan(user_id=user_id, plan_data=plan_data)

    plans = await test_plan_service.list_plans(user_id=user_id)

    assert len(plans) == 3


@pytest.mark.asyncio
async def test_list_plans_by_project(test_plan_service):
    """Test creating plans in different projects and filtering by project_id."""
    user_id = uuid4()

    await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Project 1 Plan", project_id=10, goal="A"),
    )
    await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Project 2 Plan", project_id=20, goal="B"),
    )
    await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Project 1 Plan 2", project_id=10, goal="C"),
    )

    project_10_plans = await test_plan_service.list_plans(user_id=user_id, project_id=10)
    assert len(project_10_plans) == 2
    assert all(p.project_id == 10 for p in project_10_plans)

    project_20_plans = await test_plan_service.list_plans(user_id=user_id, project_id=20)
    assert len(project_20_plans) == 1
    assert project_20_plans[0].title == "Project 2 Plan"


@pytest.mark.asyncio
async def test_list_plans_by_status(test_plan_service):
    """Test creating plans with different statuses and filtering by status."""
    user_id = uuid4()

    # Create a draft plan (default status)
    await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Draft Plan", project_id=1, goal="D"),
    )
    # Create an active plan
    await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(
            title="Active Plan", project_id=1, goal="A", status=PlanStatus.ACTIVE
        ),
    )

    drafts = await test_plan_service.list_plans(user_id=user_id, status=PlanStatus.DRAFT)
    assert len(drafts) == 1
    assert drafts[0].title == "Draft Plan"

    actives = await test_plan_service.list_plans(user_id=user_id, status=PlanStatus.ACTIVE)
    assert len(actives) == 1
    assert actives[0].title == "Active Plan"


@pytest.mark.asyncio
async def test_update_plan_title(test_plan_service):
    """Test updating only the title of a plan."""
    user_id = uuid4()

    plan = await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Original Title", project_id=1, goal="G"),
    )

    updated = await test_plan_service.update_plan(
        user_id=user_id,
        plan_id=plan.id,
        plan_data=PlanUpdate(title="Updated Title"),
    )

    assert updated is not None
    assert updated.title == "Updated Title"
    # Other fields unchanged
    assert updated.goal == "G"
    assert updated.status == PlanStatus.DRAFT


@pytest.mark.asyncio
async def test_update_plan_status_valid_transition(test_plan_service):
    """Test a valid plan status transition: draft -> active."""
    user_id = uuid4()

    plan = await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Transition Plan", project_id=1, goal="T"),
    )
    assert plan.status == PlanStatus.DRAFT

    updated = await test_plan_service.update_plan(
        user_id=user_id,
        plan_id=plan.id,
        plan_data=PlanUpdate(status=PlanStatus.ACTIVE),
    )

    assert updated is not None
    assert updated.status == PlanStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_plan_status_invalid_transition(test_plan_service):
    """Test an invalid plan status transition: draft -> completed should raise."""
    from app.exceptions import InvalidStateTransitionError

    user_id = uuid4()

    plan = await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="Bad Transition", project_id=1, goal="X"),
    )

    with pytest.raises(InvalidStateTransitionError):
        await test_plan_service.update_plan(
            user_id=user_id,
            plan_id=plan.id,
            plan_data=PlanUpdate(status=PlanStatus.COMPLETED),
        )


@pytest.mark.asyncio
async def test_delete_plan(test_plan_service):
    """Test creating, deleting, then verifying get returns None."""
    user_id = uuid4()

    plan = await test_plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title="To Delete", project_id=1, goal="Del"),
    )

    success = await test_plan_service.delete_plan(user_id=user_id, plan_id=plan.id)
    assert success is True

    retrieved = await test_plan_service.get_plan(user_id=user_id, plan_id=plan.id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_user_isolation(test_plan_service):
    """Test that a plan created by user1 is not visible to user2."""
    user1 = uuid4()
    user2 = uuid4()

    plan = await test_plan_service.create_plan(
        user_id=user1,
        plan_data=PlanCreate(title="User1 Plan", project_id=1, goal="Private"),
    )

    # user2 cannot get user1's plan
    retrieved = await test_plan_service.get_plan(user_id=user2, plan_id=plan.id)
    assert retrieved is None

    # user2 list returns empty
    user2_plans = await test_plan_service.list_plans(user_id=user2)
    assert len(user2_plans) == 0

    # user1 can see their own plan
    user1_plans = await test_plan_service.list_plans(user_id=user1)
    assert len(user1_plans) == 1
    assert user1_plans[0].title == "User1 Plan"
