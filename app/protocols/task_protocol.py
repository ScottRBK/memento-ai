from typing import List, Protocol
from uuid import UUID

from app.models.plan_models import (
    Criterion,
    CriterionCreate,
    CriterionUpdate,
    Task,
    TaskCreate,
    TaskDependency,
    TaskPriority,
    TaskState,
    TaskSummary,
    TaskUpdate,
)


class TaskRepository(Protocol):
    """Contract for Task Repository operations.

    Handles tasks + criteria + dependencies (following EntityRepository pattern
    which handles entities + relationships + links in one protocol).
    """

    # Task CRUD
    async def create_task(self, user_id: UUID, task_data: TaskCreate) -> Task: ...

    async def get_task_by_id(self, user_id: UUID, task_id: int) -> Task | None: ...

    async def list_tasks(
        self,
        user_id: UUID,
        plan_id: int,
        state: TaskState | None = None,
        priority: TaskPriority | None = None,
        assigned_agent: str | None = None,
    ) -> list[TaskSummary]: ...

    async def update_task(
        self, user_id: UUID, task_id: int, task_data: TaskUpdate
    ) -> Task: ...

    async def delete_task(self, user_id: UUID, task_id: int) -> bool: ...

    # Atomic state transition (WHERE version = expected)
    async def transition_task_state(
        self,
        user_id: UUID,
        task_id: int,
        new_state: TaskState,
        expected_version: int,
        assigned_agent: str | None = None,
    ) -> Task: ...

    # Criteria CRUD
    async def create_criterion(
        self, user_id: UUID, task_id: int, criterion_data: CriterionCreate
    ) -> Criterion: ...

    async def update_criterion(
        self, user_id: UUID, criterion_id: int, criterion_data: CriterionUpdate
    ) -> Criterion: ...

    async def delete_criterion(self, user_id: UUID, criterion_id: int) -> bool: ...

    async def get_criteria_for_task(
        self, user_id: UUID, task_id: int
    ) -> list[Criterion]: ...

    # Dependencies
    async def add_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ) -> TaskDependency: ...

    async def remove_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ) -> bool: ...

    async def get_dependencies(self, user_id: UUID, task_id: int) -> list[int]: ...

    async def get_dependents(self, user_id: UUID, task_id: int) -> list[int]: ...
