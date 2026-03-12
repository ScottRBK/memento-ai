from typing import TYPE_CHECKING, List
from uuid import UUID

from app.config.logging_config import logging
from app.config.settings import settings
from app.exceptions import (
    ConflictError,
    CyclicDependencyError,
    DependencyNotMetError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.models.activity_models import (
    ActivityEvent,
    ActorType,
    ActionType,
    EntityType,
)
from app.models.plan_models import (
    Criterion,
    CriterionCreate,
    CriterionUpdate,
    PlanStatus,
    PlanUpdate,
    Task,
    TaskCreate,
    TaskState,
    TaskSummary,
    TaskPriority,
    TaskUpdate,
    VALID_TASK_TRANSITIONS,
)
from app.protocols.task_protocol import TaskRepository
from app.services.plan_service import PlanService
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class TaskService:
    """Service layer for task operations with state machine enforcement."""

    def __init__(
        self,
        task_repo: TaskRepository,
        plan_service: PlanService,
        event_bus: "EventBus | None" = None,
    ):
        self.task_repo = task_repo
        self.plan_service = plan_service
        self._event_bus = event_bus
        logger.info("Task service initialised")

    async def _emit_event(
        self,
        user_id: UUID,
        entity_type: EntityType,
        entity_id: int,
        action: ActionType,
        snapshot: dict,
        changes: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        event = ActivityEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=changes,
            snapshot=snapshot,
            actor=ActorType.USER,
            metadata=metadata,
            user_id=str(user_id),
        )
        await self._event_bus.emit(event)

    async def create_task(self, user_id: UUID, task_data: TaskCreate) -> Task:
        """Create task with optional inline criteria and dependencies."""
        logger.info("creating task", extra={"user_id": str(user_id), "plan_id": task_data.plan_id, "title": task_data.title})

        # Validate plan exists and is not COMPLETED/ARCHIVED
        plan = await self.plan_service.get_plan(user_id=user_id, plan_id=task_data.plan_id)
        if not plan:
            raise NotFoundError(f"Plan with id {task_data.plan_id} not found")

        plan_status = PlanStatus(plan.status)
        if plan_status in (PlanStatus.COMPLETED, PlanStatus.ARCHIVED):
            raise InvalidStateTransitionError(
                f"Cannot add tasks to plan in {plan_status.value} status"
            )

        # Create the task (without criteria/deps - repo handles basic creation)
        task = await self.task_repo.create_task(user_id=user_id, task_data=task_data)

        # Create inline criteria
        if task_data.criteria:
            for criterion_data in task_data.criteria:
                await self.task_repo.create_criterion(
                    user_id=user_id, task_id=task.id, criterion_data=criterion_data
                )

        # Add dependencies with cycle detection
        if task_data.dependency_ids:
            for dep_id in task_data.dependency_ids:
                await self._validate_same_plan(user_id, task.id, dep_id, task.plan_id)
                await self._validate_no_cycle(user_id, task.id, dep_id)
                await self.task_repo.add_dependency(
                    user_id=user_id, task_id=task.id, depends_on_task_id=dep_id
                )

        # Re-fetch to get full task with criteria and deps
        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task.id)

        logger.info("task created", extra={"task_id": task.id, "plan_id": task.plan_id})
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task.id,
            action=ActionType.CREATED,
            snapshot=task.model_dump(mode="json"),
        )
        return task

    async def get_task(self, user_id: UUID, task_id: int) -> Task | None:
        logger.info("getting task", extra={"user_id": str(user_id), "task_id": task_id})
        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if task:
            logger.info("task retrieved", extra={"task_id": task_id})
        else:
            logger.info("task not found", extra={"task_id": task_id})
        return task

    async def list_tasks(
        self,
        user_id: UUID,
        plan_id: int,
        state: TaskState | None = None,
        priority: TaskPriority | None = None,
        assigned_agent: str | None = None,
    ) -> List[TaskSummary]:
        logger.info("listing tasks", extra={"plan_id": plan_id})
        tasks = await self.task_repo.list_tasks(
            user_id=user_id, plan_id=plan_id,
            state=state, priority=priority, assigned_agent=assigned_agent,
        )
        logger.info("tasks retrieved", extra={"count": len(tasks)})
        return tasks

    async def update_task(
        self, user_id: UUID, task_id: int, task_data: TaskUpdate
    ) -> Task | None:
        """PATCH for metadata only (title, description, priority). NOT for state changes."""
        logger.info("updating task", extra={"user_id": str(user_id), "task_id": task_id})

        existing = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not existing:
            return None

        changed_fields = get_changed_fields(input_model=task_data, existing_model=existing)
        if not changed_fields:
            return existing

        updated = await self.task_repo.update_task(user_id=user_id, task_id=task_id, task_data=task_data)
        logger.info("task updated", extra={"task_id": task_id})

        changes_dict = {
            field: {"old": old, "new": new}
            for field, (old, new) in changed_fields.items()
        }
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task_id,
            action=ActionType.UPDATED,
            snapshot=updated.model_dump(mode="json"),
            changes=changes_dict,
        )
        return updated

    async def delete_task(self, user_id: UUID, task_id: int) -> bool:
        logger.info("deleting task", extra={"user_id": str(user_id), "task_id": task_id})

        existing = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not existing:
            return False

        plan_id = existing.plan_id
        success = await self.task_repo.delete_task(user_id=user_id, task_id=task_id)
        if success:
            logger.info("task deleted", extra={"task_id": task_id})
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.TASK,
                entity_id=task_id,
                action=ActionType.DELETED,
                snapshot=existing.model_dump(mode="json"),
            )
            # Check plan auto-completion
            await self._check_plan_auto_completion(user_id, plan_id)
        return success

    async def transition_task(
        self,
        user_id: UUID,
        task_id: int,
        new_state: TaskState,
        expected_version: int,
    ) -> Task:
        """THE core method for state transitions with optimistic locking."""
        logger.info(
            "transitioning task",
            extra={"task_id": task_id, "new_state": new_state.value, "expected_version": expected_version},
        )

        # Fetch current task
        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not task:
            raise NotFoundError(f"Task with id {task_id} not found")

        # Verify version (optimistic locking)
        if task.version != expected_version:
            raise ConflictError(
                f"Version mismatch: expected {expected_version}, got {task.version}. "
                f"Task was modified by another agent."
            )

        # Validate state transition
        current_state = TaskState(task.state)
        valid_targets = VALID_TASK_TRANSITIONS.get(current_state, set())
        if new_state not in valid_targets:
            raise InvalidStateTransitionError(
                f"Cannot transition task from {current_state.value} to {new_state.value}. "
                f"Valid transitions: {[s.value for s in valid_targets]}"
            )

        # If → doing: validate all dependencies are done
        if new_state == TaskState.DOING:
            await self._validate_dependencies_met(user_id, task)

        # If → done: validate all criteria are met (tasks with zero criteria CAN be marked done)
        if new_state == TaskState.DONE:
            await self._validate_all_criteria_met(user_id, task)

        # Atomic update
        updated = await self.task_repo.transition_task_state(
            user_id=user_id,
            task_id=task_id,
            new_state=new_state,
            expected_version=expected_version,
        )

        logger.info(
            "task transitioned",
            extra={"task_id": task_id, "old_state": current_state.value, "new_state": new_state.value},
        )

        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task_id,
            action=ActionType.UPDATED,
            snapshot=updated.model_dump(mode="json"),
            changes={"state": {"old": current_state.value, "new": new_state.value}},
        )

        # If task → done/cancelled: check plan auto-completion
        if new_state in (TaskState.DONE, TaskState.CANCELLED):
            await self._check_plan_auto_completion(user_id, task.plan_id)

        return updated

    async def claim_task(
        self,
        user_id: UUID,
        task_id: int,
        agent_id: str,
        expected_version: int,
    ) -> Task:
        """Convenience wrapper: claim task by setting agent and transitioning to doing."""
        logger.info(
            "claiming task",
            extra={"task_id": task_id, "agent_id": agent_id, "expected_version": expected_version},
        )

        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not task:
            raise NotFoundError(f"Task with id {task_id} not found")

        if task.version != expected_version:
            raise ConflictError(
                f"Version mismatch: expected {expected_version}, got {task.version}. "
                f"Task was modified by another agent."
            )

        current_state = TaskState(task.state)
        if current_state not in (TaskState.TODO, TaskState.WAITING):
            raise InvalidStateTransitionError(
                f"Cannot claim task in {current_state.value} state. Must be todo or waiting."
            )

        # Validate dependencies met
        await self._validate_dependencies_met(user_id, task)

        # Atomic: set assigned_agent + state=doing + version+=1
        updated = await self.task_repo.transition_task_state(
            user_id=user_id,
            task_id=task_id,
            new_state=TaskState.DOING,
            expected_version=expected_version,
            assigned_agent=agent_id,
        )

        logger.info("task claimed", extra={"task_id": task_id, "agent_id": agent_id})

        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.TASK,
            entity_id=task_id,
            action=ActionType.UPDATED,
            snapshot=updated.model_dump(mode="json"),
            changes={
                "state": {"old": current_state.value, "new": TaskState.DOING.value},
                "assigned_agent": {"old": task.assigned_agent, "new": agent_id},
            },
        )
        return updated

    # ---- Criteria ----

    async def add_criterion(
        self, user_id: UUID, task_id: int, criterion_data: CriterionCreate
    ) -> Criterion:
        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not task:
            raise NotFoundError(f"Task with id {task_id} not found")
        if TaskState(task.state) == TaskState.DONE:
            raise InvalidStateTransitionError("Cannot add criteria to a completed task")

        criterion = await self.task_repo.create_criterion(
            user_id=user_id, task_id=task_id, criterion_data=criterion_data
        )
        logger.info("criterion added", extra={"criterion_id": criterion.id, "task_id": task_id})
        return criterion

    async def update_criterion(
        self, user_id: UUID, criterion_id: int, criterion_data: CriterionUpdate
    ) -> Criterion:
        criterion = await self.task_repo.update_criterion(
            user_id=user_id, criterion_id=criterion_id, criterion_data=criterion_data
        )
        logger.info("criterion updated", extra={"criterion_id": criterion_id})
        return criterion

    async def delete_criterion(self, user_id: UUID, criterion_id: int) -> bool:
        success = await self.task_repo.delete_criterion(user_id=user_id, criterion_id=criterion_id)
        if success:
            logger.info("criterion deleted", extra={"criterion_id": criterion_id})
        return success

    # ---- Dependencies ----

    async def add_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ):
        # Validate both tasks exist
        task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=task_id)
        if not task:
            raise NotFoundError(f"Task with id {task_id} not found")

        dep_task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=depends_on_task_id)
        if not dep_task:
            raise NotFoundError(f"Task with id {depends_on_task_id} not found")

        # Validate same plan
        await self._validate_same_plan(user_id, task_id, depends_on_task_id, task.plan_id)

        # Cycle detection
        await self._validate_no_cycle(user_id, task_id, depends_on_task_id)

        dep = await self.task_repo.add_dependency(
            user_id=user_id, task_id=task_id, depends_on_task_id=depends_on_task_id
        )
        logger.info("dependency added", extra={"task_id": task_id, "depends_on": depends_on_task_id})
        return dep

    async def remove_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ) -> bool:
        success = await self.task_repo.remove_dependency(
            user_id=user_id, task_id=task_id, depends_on_task_id=depends_on_task_id
        )
        if success:
            logger.info("dependency removed", extra={"task_id": task_id, "depends_on": depends_on_task_id})
        return success

    # ---- Private Helpers ----

    async def _validate_dependencies_met(self, user_id: UUID, task: Task) -> None:
        """Check all dependencies are in done state."""
        dep_ids = task.dependency_ids
        if not dep_ids:
            return

        for dep_id in dep_ids:
            dep_task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=dep_id)
            if not dep_task or TaskState(dep_task.state) != TaskState.DONE:
                raise DependencyNotMetError(
                    f"Dependency task {dep_id} is not done "
                    f"(state: {dep_task.state if dep_task else 'not found'})"
                )

    async def _validate_all_criteria_met(self, user_id: UUID, task: Task) -> None:
        """Check all criteria have met=True. Tasks with zero criteria CAN be marked done."""
        criteria = await self.task_repo.get_criteria_for_task(user_id=user_id, task_id=task.id)
        if not criteria:
            return  # Zero criteria = can be done

        unmet = [c for c in criteria if not c.met]
        if unmet:
            raise InvalidStateTransitionError(
                f"Cannot mark task as done: {len(unmet)} acceptance criteria not met. "
                f"Unmet: {[c.description[:50] for c in unmet]}"
            )

    async def _validate_no_cycle(self, user_id: UUID, task_id: int, new_dep_id: int) -> None:
        """BFS from new_dep_id following existing 'depends_on' edges.
        If we reach task_id, adding this edge would create a cycle."""
        if task_id == new_dep_id:
            raise CyclicDependencyError("A task cannot depend on itself")

        visited: set[int] = set()
        queue: list[int] = [new_dep_id]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            deps = await self.task_repo.get_dependencies(user_id, current)
            for dep_id in deps:
                if dep_id == task_id:
                    raise CyclicDependencyError(
                        f"Adding dependency {task_id} -> {new_dep_id} would create a cycle "
                        f"(path exists from {new_dep_id} back to {task_id})"
                    )
                queue.append(dep_id)

    async def _validate_same_plan(
        self, user_id: UUID, task_id: int, dep_task_id: int, expected_plan_id: int
    ) -> None:
        """Validate that the dependency task belongs to the same plan."""
        dep_task = await self.task_repo.get_task_by_id(user_id=user_id, task_id=dep_task_id)
        if not dep_task:
            raise NotFoundError(f"Task with id {dep_task_id} not found")
        if dep_task.plan_id != expected_plan_id:
            raise ValueError(
                f"Task {dep_task_id} belongs to plan {dep_task.plan_id}, "
                f"not plan {expected_plan_id}. Dependencies must be within the same plan."
            )

    async def _check_plan_auto_completion(self, user_id: UUID, plan_id: int) -> None:
        """If all tasks in the plan are done/cancelled (with at least one done),
        auto-transition plan to COMPLETED."""
        tasks = await self.task_repo.list_tasks(user_id=user_id, plan_id=plan_id)
        if not tasks:
            return

        all_terminal = all(
            TaskState(t.state) in (TaskState.DONE, TaskState.CANCELLED)
            for t in tasks
        )
        has_done = any(TaskState(t.state) == TaskState.DONE for t in tasks)

        if all_terminal and has_done:
            plan = await self.plan_service.get_plan(user_id=user_id, plan_id=plan_id)
            if plan and PlanStatus(plan.status) == PlanStatus.ACTIVE:
                logger.info("auto-completing plan", extra={"plan_id": plan_id})
                await self.plan_service.update_plan(
                    user_id=user_id,
                    plan_id=plan_id,
                    plan_data=PlanUpdate(status=PlanStatus.COMPLETED),
                )
