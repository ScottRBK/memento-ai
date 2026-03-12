"""
Integration tests for TaskService with in-memory stubs
"""

import pytest
from uuid import uuid4

from app.models.plan_models import (
    PlanCreate,
    PlanUpdate,
    PlanStatus,
    TaskCreate,
    TaskUpdate,
    TaskState,
    TaskPriority,
    CriterionCreate,
    CriterionUpdate,
)
from app.exceptions import (
    ConflictError,
    CyclicDependencyError,
    DependencyNotMetError,
    InvalidStateTransitionError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_active_plan(plan_service, user_id, project_id=1, title="Test Plan"):
    """Helper: create a plan and transition it to ACTIVE so tasks can be added."""
    plan = await plan_service.create_plan(
        user_id=user_id,
        plan_data=PlanCreate(title=title, project_id=project_id, goal="test"),
    )
    plan = await plan_service.update_plan(
        user_id=user_id,
        plan_id=plan.id,
        plan_data=PlanUpdate(status=PlanStatus.ACTIVE),
    )
    return plan


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_basic(test_task_service):
    """Test creating a task with inline criteria."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task_data = TaskCreate(
        title="Implement login",
        plan_id=plan.id,
        description="Build the login page",
        priority=TaskPriority.P1,
        criteria=[
            CriterionCreate(description="Unit tests pass"),
            CriterionCreate(description="E2E test pass"),
        ],
    )
    task = await task_service.create_task(user_id=user_id, task_data=task_data)

    assert task is not None
    assert task.id is not None
    assert task.title == "Implement login"
    assert task.plan_id == plan.id
    assert task.state == TaskState.TODO
    assert task.priority == TaskPriority.P1
    assert task.version == 1
    assert len(task.criteria) == 2
    assert task.criteria[0].description == "Unit tests pass"
    assert task.criteria[1].description == "E2E test pass"
    assert task.created_at is not None


@pytest.mark.asyncio
async def test_get_task_with_criteria(test_task_service):
    """Test creating a task with criteria, then getting it back and verifying criteria."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    created = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(
            title="Task with criteria",
            plan_id=plan.id,
            criteria=[CriterionCreate(description="Acceptance criterion A")],
        ),
    )

    retrieved = await task_service.get_task(user_id=user_id, task_id=created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert len(retrieved.criteria) == 1
    assert retrieved.criteria[0].description == "Acceptance criterion A"
    assert retrieved.criteria[0].met is False


@pytest.mark.asyncio
async def test_list_tasks_by_state(test_task_service):
    """Test creating tasks and filtering by state."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    # Create two tasks (both start as TODO)
    t1 = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Task 1", plan_id=plan.id),
    )
    await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Task 2", plan_id=plan.id),
    )

    # Transition t1 to DOING
    await task_service.transition_task(
        user_id=user_id, task_id=t1.id, new_state=TaskState.DOING, expected_version=1
    )

    todo_tasks = await task_service.list_tasks(
        user_id=user_id, plan_id=plan.id, state=TaskState.TODO
    )
    doing_tasks = await task_service.list_tasks(
        user_id=user_id, plan_id=plan.id, state=TaskState.DOING
    )

    assert len(todo_tasks) == 1
    assert todo_tasks[0].title == "Task 2"
    assert len(doing_tasks) == 1
    assert doing_tasks[0].title == "Task 1"


@pytest.mark.asyncio
async def test_update_task_metadata(test_task_service):
    """Test updating task title and priority via PATCH."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Original", plan_id=plan.id, priority=TaskPriority.P2),
    )

    updated = await task_service.update_task(
        user_id=user_id,
        task_id=task.id,
        task_data=TaskUpdate(title="Renamed", priority=TaskPriority.P0),
    )

    assert updated is not None
    assert updated.title == "Renamed"
    assert updated.priority == TaskPriority.P0
    # State untouched
    assert updated.state == TaskState.TODO


@pytest.mark.asyncio
async def test_transition_task_todo_to_doing(test_task_service):
    """Test valid transition: todo -> doing."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Start work", plan_id=plan.id),
    )

    transitioned = await task_service.transition_task(
        user_id=user_id,
        task_id=task.id,
        new_state=TaskState.DOING,
        expected_version=1,
    )

    assert transitioned.state == TaskState.DOING
    assert transitioned.version == 2


@pytest.mark.asyncio
async def test_transition_task_invalid(test_task_service):
    """Test invalid transition: done -> doing should raise InvalidStateTransitionError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Finish me", plan_id=plan.id),
    )

    # todo -> doing (v1 -> v2)
    await task_service.transition_task(
        user_id=user_id, task_id=task.id, new_state=TaskState.DOING, expected_version=1
    )
    # doing -> done (v2 -> v3)
    await task_service.transition_task(
        user_id=user_id, task_id=task.id, new_state=TaskState.DONE, expected_version=2
    )

    # done -> doing is NOT valid (done can only go to todo)
    with pytest.raises(InvalidStateTransitionError):
        await task_service.transition_task(
            user_id=user_id,
            task_id=task.id,
            new_state=TaskState.DOING,
            expected_version=3,
        )


@pytest.mark.asyncio
async def test_claim_task_success(test_task_service):
    """Test successfully claiming a task in TODO state."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Claimable", plan_id=plan.id),
    )

    claimed = await task_service.claim_task(
        user_id=user_id,
        task_id=task.id,
        agent_id="agent-007",
        expected_version=1,
    )

    assert claimed.state == TaskState.DOING
    assert claimed.assigned_agent == "agent-007"
    assert claimed.version == 2


@pytest.mark.asyncio
async def test_claim_task_version_conflict(test_task_service):
    """Test that two claims with the same version fail on the second attempt."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Contested", plan_id=plan.id),
    )

    # First claim succeeds (version goes from 1 to 2)
    await task_service.claim_task(
        user_id=user_id,
        task_id=task.id,
        agent_id="agent-A",
        expected_version=1,
    )

    # Second claim with stale version=1 should fail
    with pytest.raises(ConflictError):
        await task_service.claim_task(
            user_id=user_id,
            task_id=task.id,
            agent_id="agent-B",
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_transition_to_done_with_all_criteria_met(test_task_service):
    """Test that a task with all criteria met can transition to DONE."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(
            title="With criteria",
            plan_id=plan.id,
            criteria=[
                CriterionCreate(description="Criterion 1"),
                CriterionCreate(description="Criterion 2"),
            ],
        ),
    )

    # Mark both criteria as met
    for criterion in task.criteria:
        await task_service.update_criterion(
            user_id=user_id,
            criterion_id=criterion.id,
            criterion_data=CriterionUpdate(met=True),
        )

    # todo -> doing -> done
    await task_service.transition_task(
        user_id=user_id, task_id=task.id, new_state=TaskState.DOING, expected_version=1
    )
    done_task = await task_service.transition_task(
        user_id=user_id, task_id=task.id, new_state=TaskState.DONE, expected_version=2
    )

    assert done_task.state == TaskState.DONE


@pytest.mark.asyncio
async def test_transition_to_done_with_unmet_criteria(test_task_service):
    """Test that transitioning to DONE with unmet criteria raises InvalidStateTransitionError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(
            title="Incomplete criteria",
            plan_id=plan.id,
            criteria=[CriterionCreate(description="Not met yet")],
        ),
    )

    # todo -> doing
    await task_service.transition_task(
        user_id=user_id, task_id=task.id, new_state=TaskState.DOING, expected_version=1
    )

    # doing -> done should fail because criterion is not met
    with pytest.raises(InvalidStateTransitionError):
        await task_service.transition_task(
            user_id=user_id,
            task_id=task.id,
            new_state=TaskState.DONE,
            expected_version=2,
        )


@pytest.mark.asyncio
async def test_transition_to_doing_with_unmet_deps(test_task_service):
    """Test that transitioning to DOING with unmet dependencies raises DependencyNotMetError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    # Create prerequisite task (stays in TODO)
    prereq = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Prerequisite", plan_id=plan.id),
    )

    # Create dependent task that depends on prereq
    dependent = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(
            title="Dependent",
            plan_id=plan.id,
            dependency_ids=[prereq.id],
        ),
    )

    # Trying to transition dependent to DOING should fail since prereq is not DONE
    with pytest.raises(DependencyNotMetError):
        await task_service.transition_task(
            user_id=user_id,
            task_id=dependent.id,
            new_state=TaskState.DOING,
            expected_version=1,
        )


@pytest.mark.asyncio
async def test_cycle_detection_self(test_task_service):
    """Test that a task depending on itself raises CyclicDependencyError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Self loop", plan_id=plan.id),
    )

    with pytest.raises(CyclicDependencyError):
        await task_service.add_dependency(
            user_id=user_id, task_id=task.id, depends_on_task_id=task.id
        )


@pytest.mark.asyncio
async def test_cycle_detection_direct(test_task_service):
    """Test direct cycle: A->B then B->A raises CyclicDependencyError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    a = await task_service.create_task(
        user_id=user_id, task_data=TaskCreate(title="A", plan_id=plan.id)
    )
    b = await task_service.create_task(
        user_id=user_id, task_data=TaskCreate(title="B", plan_id=plan.id)
    )

    # A depends on B
    await task_service.add_dependency(
        user_id=user_id, task_id=a.id, depends_on_task_id=b.id
    )

    # B depends on A => cycle
    with pytest.raises(CyclicDependencyError):
        await task_service.add_dependency(
            user_id=user_id, task_id=b.id, depends_on_task_id=a.id
        )


@pytest.mark.asyncio
async def test_cycle_detection_transitive(test_task_service):
    """Test transitive cycle: A->B->C then C->A raises CyclicDependencyError."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    a = await task_service.create_task(
        user_id=user_id, task_data=TaskCreate(title="A", plan_id=plan.id)
    )
    b = await task_service.create_task(
        user_id=user_id, task_data=TaskCreate(title="B", plan_id=plan.id)
    )
    c = await task_service.create_task(
        user_id=user_id, task_data=TaskCreate(title="C", plan_id=plan.id)
    )

    # A depends on B
    await task_service.add_dependency(
        user_id=user_id, task_id=a.id, depends_on_task_id=b.id
    )
    # B depends on C
    await task_service.add_dependency(
        user_id=user_id, task_id=b.id, depends_on_task_id=c.id
    )

    # C depends on A => transitive cycle
    with pytest.raises(CyclicDependencyError):
        await task_service.add_dependency(
            user_id=user_id, task_id=c.id, depends_on_task_id=a.id
        )


@pytest.mark.asyncio
async def test_add_delete_criteria(test_task_service):
    """Test adding then deleting a criterion."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Criteria ops", plan_id=plan.id),
    )

    # Add criterion
    criterion = await task_service.add_criterion(
        user_id=user_id,
        task_id=task.id,
        criterion_data=CriterionCreate(description="Must pass code review"),
    )
    assert criterion.id is not None
    assert criterion.description == "Must pass code review"
    assert criterion.met is False

    # Delete criterion
    deleted = await task_service.delete_criterion(
        user_id=user_id, criterion_id=criterion.id
    )
    assert deleted is True

    # Verify it's gone
    refreshed_task = await task_service.get_task(user_id=user_id, task_id=task.id)
    assert len(refreshed_task.criteria) == 0


@pytest.mark.asyncio
async def test_verify_criterion(test_task_service):
    """Test marking a criterion as met."""
    task_service, plan_service = test_task_service
    user_id = uuid4()
    plan = await _create_active_plan(plan_service, user_id)

    task = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(
            title="Verify criterion",
            plan_id=plan.id,
            criteria=[CriterionCreate(description="Tests pass")],
        ),
    )

    criterion_id = task.criteria[0].id

    updated_criterion = await task_service.update_criterion(
        user_id=user_id,
        criterion_id=criterion_id,
        criterion_data=CriterionUpdate(met=True),
    )

    assert updated_criterion.met is True
    assert updated_criterion.met_at is not None


@pytest.mark.asyncio
async def test_plan_auto_completion(test_task_service):
    """Test that completing all tasks in an ACTIVE plan auto-transitions it to COMPLETED."""
    task_service, plan_service = test_task_service
    user_id = uuid4()

    # Create plan as draft, transition to active
    plan = await _create_active_plan(plan_service, user_id)
    assert plan.status == PlanStatus.ACTIVE

    # Create two tasks
    t1 = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Task 1", plan_id=plan.id),
    )
    t2 = await task_service.create_task(
        user_id=user_id,
        task_data=TaskCreate(title="Task 2", plan_id=plan.id),
    )

    # Complete first task: todo -> doing -> done
    await task_service.transition_task(
        user_id=user_id, task_id=t1.id, new_state=TaskState.DOING, expected_version=1
    )
    await task_service.transition_task(
        user_id=user_id, task_id=t1.id, new_state=TaskState.DONE, expected_version=2
    )

    # Plan should still be ACTIVE (not all tasks done)
    plan_after_t1 = await plan_service.get_plan(user_id=user_id, plan_id=plan.id)
    assert plan_after_t1.status == PlanStatus.ACTIVE

    # Complete second task: todo -> doing -> done
    await task_service.transition_task(
        user_id=user_id, task_id=t2.id, new_state=TaskState.DOING, expected_version=1
    )
    await task_service.transition_task(
        user_id=user_id, task_id=t2.id, new_state=TaskState.DONE, expected_version=2
    )

    # Plan should now be auto-completed
    plan_after_all = await plan_service.get_plan(user_id=user_id, plan_id=plan.id)
    assert plan_after_all.status == PlanStatus.COMPLETED


@pytest.mark.asyncio
async def test_user_isolation(test_task_service):
    """Test that a task created by user1 is not visible to user2."""
    task_service, plan_service = test_task_service
    user1 = uuid4()
    user2 = uuid4()

    plan = await _create_active_plan(plan_service, user1)

    task = await task_service.create_task(
        user_id=user1,
        task_data=TaskCreate(title="User1 Task", plan_id=plan.id),
    )

    # user2 cannot get user1's task
    retrieved = await task_service.get_task(user_id=user2, task_id=task.id)
    assert retrieved is None

    # user2 list for the same plan_id returns empty
    user2_tasks = await task_service.list_tasks(user_id=user2, plan_id=plan.id)
    assert len(user2_tasks) == 0
