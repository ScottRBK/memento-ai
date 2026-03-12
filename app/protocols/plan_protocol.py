from typing import List, Protocol
from uuid import UUID

from app.models.plan_models import (
    Plan,
    PlanCreate,
    PlanStatus,
    PlanSummary,
    PlanUpdate,
)


class PlanRepository(Protocol):
    """Contract for Plan Repository operations."""

    async def create_plan(self, user_id: UUID, plan_data: PlanCreate) -> Plan: ...

    async def get_plan_by_id(self, user_id: UUID, plan_id: int) -> Plan | None: ...

    async def list_plans(
        self,
        user_id: UUID,
        project_id: int | None = None,
        status: PlanStatus | None = None,
    ) -> List[PlanSummary]: ...

    async def update_plan(
        self, user_id: UUID, plan_id: int, plan_data: PlanUpdate
    ) -> Plan: ...

    async def delete_plan(self, user_id: UUID, plan_id: int) -> bool: ...
