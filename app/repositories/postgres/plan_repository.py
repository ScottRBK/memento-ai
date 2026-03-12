"""Plan repository for Postgres data access operations"""

from datetime import datetime, timezone
from typing import List
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from app.config.logging_config import logging
from app.exceptions import NotFoundError
from app.models.plan_models import (
    Plan,
    PlanCreate,
    PlanStatus,
    PlanSummary,
    PlanUpdate,
)
from app.repositories.postgres.postgres_adapter import PostgresDatabaseAdapter
from app.repositories.postgres.postgres_tables import PlansTable

logger = logging.getLogger(__name__)


class PostgresPlanRepository:
    """Repository for Plan entity operations in Postgres."""

    def __init__(self, db_adapter: PostgresDatabaseAdapter):
        self.db_adapter = db_adapter
        logger.info("Plan repository initialized")

    async def create_plan(self, user_id: UUID, plan_data: PlanCreate) -> Plan:
        logger.info("Creating plan", extra={"user_id": str(user_id), "title": plan_data.title})

        async with self.db_adapter.session(user_id) as session:
            data = plan_data.model_dump(exclude={"criteria", "dependency_ids"})
            new_plan = PlansTable(**data, user_id=user_id)
            session.add(new_plan)
            await session.flush()
            await session.refresh(new_plan, attribute_names=["tasks"])
            plan = Plan.model_validate(new_plan)
            logger.info("Plan created", extra={"plan_id": plan.id})
            return plan

    async def get_plan_by_id(self, user_id: UUID, plan_id: int) -> Plan | None:
        logger.info("Getting plan by ID", extra={"plan_id": plan_id})

        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(PlansTable)
                .options(selectinload(PlansTable.tasks))
                .where(PlansTable.user_id == user_id, PlansTable.id == plan_id)
            )
            result = await session.execute(stmt)
            plan_orm = result.scalar_one_or_none()
            if plan_orm:
                return Plan.model_validate(plan_orm)
            return None

    async def list_plans(
        self,
        user_id: UUID,
        project_id: int | None = None,
        status: PlanStatus | None = None,
    ) -> List[PlanSummary]:
        logger.info("Listing plans", extra={"user_id": str(user_id)})

        async with self.db_adapter.session(user_id) as session:
            stmt = (
                select(PlansTable)
                .options(selectinload(PlansTable.tasks))
                .where(PlansTable.user_id == user_id)
            )
            if project_id is not None:
                stmt = stmt.where(PlansTable.project_id == project_id)
            if status:
                stmt = stmt.where(PlansTable.status == status.value)
            stmt = stmt.order_by(PlansTable.created_at.desc())

            result = await session.execute(stmt)
            plans_orm = result.scalars().all()
            return [PlanSummary.model_validate(p) for p in plans_orm]

    async def update_plan(
        self, user_id: UUID, plan_id: int, plan_data: PlanUpdate
    ) -> Plan:
        logger.info("Updating plan", extra={"plan_id": plan_id})

        async with self.db_adapter.session(user_id) as session:
            update_data = plan_data.model_dump(exclude_unset=True)
            if not update_data:
                stmt = (
                    select(PlansTable)
                    .options(selectinload(PlansTable.tasks))
                    .where(PlansTable.user_id == user_id, PlansTable.id == plan_id)
                )
                result = await session.execute(stmt)
                plan_orm = result.scalar_one_or_none()
                if not plan_orm:
                    raise NotFoundError(f"Plan with id {plan_id} not found")
                return Plan.model_validate(plan_orm)

            update_data["updated_at"] = datetime.now(timezone.utc)
            stmt = (
                update(PlansTable)
                .where(PlansTable.user_id == user_id, PlansTable.id == plan_id)
                .values(**update_data)
                .returning(PlansTable)
            )
            result = await session.execute(stmt)
            plan_orm = result.scalar_one_or_none()
            if not plan_orm:
                raise NotFoundError(f"Plan with id {plan_id} not found")
            await session.refresh(plan_orm, attribute_names=["tasks"])
            return Plan.model_validate(plan_orm)

    async def delete_plan(self, user_id: UUID, plan_id: int) -> bool:
        logger.info("Deleting plan", extra={"plan_id": plan_id})

        async with self.db_adapter.session(user_id) as session:
            stmt = delete(PlansTable).where(
                PlansTable.user_id == user_id, PlansTable.id == plan_id
            )
            result = await session.execute(stmt)
            return result.rowcount > 0
