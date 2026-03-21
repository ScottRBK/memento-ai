"""Task repository for Postgres data access operations"""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from app.config.logging_config import logging
from app.exceptions import ConflictError, NotFoundError
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
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.postgres_tables import (
    CriteriaTable,
    TaskDependenciesTable,
    TasksTable,
)

logger = logging.getLogger(__name__)


class PostgresTaskRepository:
    """Repository for Task, Criterion, and TaskDependency operations in Postgres."""

    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        self.db_adapter = db_adapter
        logger.info("Task repository initialized")

    # ---- Task CRUD ----

    async def create_task(self, user_id: UUID, task_data: TaskCreate) -> Task:
        logger.info("Creating task", extra={"plan_id": task_data.plan_id, "title": task_data.title})

        async with self.db_adapter.session(user_id) as session:
            data = task_data.model_dump(exclude={"criteria", "dependency_ids"})
            new_task = TasksTable(**data, user_id=user_id)
            session.add(new_task)
            await session.flush()
            await session.refresh(new_task, attribute_names=["criteria", "depends_on"])
            return Task.model_validate(new_task)

    async def get_task_by_id(self, user_id: UUID, task_id: int) -> Task | None:
        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(TasksTable)
                .options(
                    selectinload(TasksTable.criteria),
                    selectinload(TasksTable.depends_on),
                )
                .where(TasksTable.user_id == user_id, TasksTable.id == task_id)
            )
            result = await session.execute(stmt)
            task_orm = result.scalar_one_or_none()
            if task_orm:
                return Task.model_validate(task_orm)
            return None

    async def list_tasks(
        self,
        user_id: UUID,
        plan_id: int,
        state: TaskState | None = None,
        priority: TaskPriority | None = None,
        assigned_agent: str | None = None,
    ) -> list[TaskSummary]:
        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(TasksTable)
                .options(
                    selectinload(TasksTable.criteria),
                    selectinload(TasksTable.depends_on),
                )
                .where(TasksTable.user_id == user_id, TasksTable.plan_id == plan_id)
            )
            if state:
                stmt = stmt.where(TasksTable.state == state.value)
            if priority:
                stmt = stmt.where(TasksTable.priority == priority.value)
            if assigned_agent:
                stmt = stmt.where(TasksTable.assigned_agent == assigned_agent)
            stmt = stmt.order_by(TasksTable.created_at.asc())

            result = await session.execute(stmt)
            tasks_orm = result.scalars().all()

            summaries = []
            for t in tasks_orm:
                criteria_met = sum(1 for c in t.criteria if c.met)
                criteria_total = len(t.criteria)
                dep_ids = [d.depends_on_task_id for d in t.depends_on]
                blocked = False
                if dep_ids:
                    for dep_id in dep_ids:
                        dep_stmt = select(TasksTable.state).where(
                            TasksTable.user_id == user_id,
                            TasksTable.id == dep_id,
                        )
                        dep_result = await session.execute(dep_stmt)
                        dep_state = dep_result.scalar_one_or_none()
                        if dep_state != TaskState.DONE.value:
                            blocked = True
                            break

                summaries.append(TaskSummary(
                    id=t.id,
                    title=t.title,
                    plan_id=t.plan_id,
                    state=TaskState(t.state),
                    priority=TaskPriority(t.priority),
                    assigned_agent=t.assigned_agent,
                    version=t.version,
                    criteria_met=criteria_met,
                    criteria_total=criteria_total,
                    blocked=blocked,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                ))
            return summaries

    async def update_task(
        self, user_id: UUID, task_id: int, task_data: TaskUpdate
    ) -> Task:
        async with self.db_adapter.session(user_id) as session:
            update_data = task_data.model_dump(exclude_unset=True)
            if not update_data:
                return await self.get_task_by_id(user_id, task_id)

            update_data["updated_at"] = datetime.now(timezone.utc)
            stmt = (
                update(TasksTable)
                .where(TasksTable.user_id == user_id, TasksTable.id == task_id)
                .values(**update_data)
                .returning(TasksTable)
            )
            result = await session.execute(stmt)
            task_orm = result.scalar_one_or_none()
            if not task_orm:
                raise NotFoundError(f"Task with id {task_id} not found")
            await session.refresh(task_orm, attribute_names=["criteria", "depends_on"])
            return Task.model_validate(task_orm)

    async def delete_task(self, user_id: UUID, task_id: int) -> bool:
        async with self.db_adapter.session(user_id) as session:
            stmt = delete(TasksTable).where(
                TasksTable.user_id == user_id, TasksTable.id == task_id
            )
            result = await session.execute(stmt)
            return result.rowcount > 0

    # ---- Atomic state transition ----

    async def transition_task_state(
        self,
        user_id: UUID,
        task_id: int,
        new_state: TaskState,
        expected_version: int,
        assigned_agent: str | None = None,
    ) -> Task:
        async with self.db_adapter.session(user_id) as session:
            now = datetime.now(timezone.utc)
            values = {
                "state": new_state.value,
                "version": expected_version + 1,
                "updated_at": now,
            }
            if assigned_agent is not None:
                values["assigned_agent"] = assigned_agent

            stmt = (
                update(TasksTable)
                .where(
                    TasksTable.user_id == user_id,
                    TasksTable.id == task_id,
                    TasksTable.version == expected_version,
                )
                .values(**values)
                .returning(TasksTable)
            )
            result = await session.execute(stmt)
            task_orm = result.scalar_one_or_none()

            if task_orm is None:
                check = await session.execute(
                    select(TasksTable).where(
                        TasksTable.user_id == user_id,
                        TasksTable.id == task_id,
                    )
                )
                exists = check.scalar_one_or_none()
                if not exists:
                    raise NotFoundError(f"Task with id {task_id} not found")
                raise ConflictError(
                    f"Version conflict for task {task_id}: expected {expected_version}, "
                    f"current is {exists.version}"
                )

            await session.refresh(task_orm, attribute_names=["criteria", "depends_on"])
            return Task.model_validate(task_orm)

    # ---- Criteria CRUD ----

    async def create_criterion(
        self, user_id: UUID, task_id: int, criterion_data: CriterionCreate
    ) -> Criterion:
        async with self.db_adapter.session(user_id) as session:
            new_criterion = CriteriaTable(
                user_id=user_id,
                task_id=task_id,
                description=criterion_data.description,
            )
            session.add(new_criterion)
            await session.flush()
            return Criterion.model_validate(new_criterion)

    async def update_criterion(
        self, user_id: UUID, criterion_id: int, criterion_data: CriterionUpdate
    ) -> Criterion:
        async with self.db_adapter.session(user_id) as session:
            update_data = criterion_data.model_dump(exclude_unset=True)
            if not update_data:
                stmt = select(CriteriaTable).where(
                    CriteriaTable.user_id == user_id,
                    CriteriaTable.id == criterion_id,
                )
                result = await session.execute(stmt)
                c = result.scalar_one_or_none()
                if not c:
                    raise NotFoundError(f"Criterion with id {criterion_id} not found")
                return Criterion.model_validate(c)

            if update_data.get("met") is True:
                update_data["met_at"] = datetime.now(timezone.utc)
            elif update_data.get("met") is False:
                update_data["met_at"] = None

            update_data["updated_at"] = datetime.now(timezone.utc)

            stmt = (
                update(CriteriaTable)
                .where(
                    CriteriaTable.user_id == user_id,
                    CriteriaTable.id == criterion_id,
                )
                .values(**update_data)
                .returning(CriteriaTable)
            )
            result = await session.execute(stmt)
            c = result.scalar_one_or_none()
            if not c:
                raise NotFoundError(f"Criterion with id {criterion_id} not found")
            return Criterion.model_validate(c)

    async def delete_criterion(self, user_id: UUID, criterion_id: int) -> bool:
        async with self.db_adapter.session(user_id) as session:
            stmt = delete(CriteriaTable).where(
                CriteriaTable.user_id == user_id,
                CriteriaTable.id == criterion_id,
            )
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def get_criteria_for_task(
        self, user_id: UUID, task_id: int
    ) -> list[Criterion]:
        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(CriteriaTable)
                .where(
                    CriteriaTable.user_id == user_id,
                    CriteriaTable.task_id == task_id,
                )
                .order_by(CriteriaTable.created_at.asc())
            )
            result = await session.execute(stmt)
            return [Criterion.model_validate(c) for c in result.scalars().all()]

    # ---- Dependencies ----

    async def add_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ) -> TaskDependency:
        async with self.db_adapter.session(user_id) as session:
            dep = TaskDependenciesTable(
                user_id=user_id,
                task_id=task_id,
                depends_on_task_id=depends_on_task_id,
            )
            session.add(dep)
            await session.flush()
            return TaskDependency.model_validate(dep)

    async def remove_dependency(
        self, user_id: UUID, task_id: int, depends_on_task_id: int
    ) -> bool:
        async with self.db_adapter.session(user_id) as session:
            stmt = delete(TaskDependenciesTable).where(
                TaskDependenciesTable.user_id == user_id,
                TaskDependenciesTable.task_id == task_id,
                TaskDependenciesTable.depends_on_task_id == depends_on_task_id,
            )
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def get_dependencies(self, user_id: UUID, task_id: int) -> list[int]:
        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(TaskDependenciesTable.depends_on_task_id)
                .where(
                    TaskDependenciesTable.user_id == user_id,
                    TaskDependenciesTable.task_id == task_id,
                )
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    async def get_dependents(self, user_id: UUID, task_id: int) -> list[int]:
        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(TaskDependenciesTable.task_id)
                .where(
                    TaskDependenciesTable.user_id == user_id,
                    TaskDependenciesTable.depends_on_task_id == task_id,
                )
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]
