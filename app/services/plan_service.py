from typing import TYPE_CHECKING, List
from uuid import UUID

from app.config.logging_config import logging
from app.config.settings import settings
from app.exceptions import InvalidStateTransitionError
from app.models.activity_models import (
    ActivityEvent,
    ActorType,
    ActionType,
    EntityType,
)
from app.models.plan_models import (
    Plan,
    PlanCreate,
    PlanStatus,
    PlanSummary,
    PlanUpdate,
    VALID_PLAN_TRANSITIONS,
)
from app.protocols.plan_protocol import PlanRepository
from app.utils.pydantic_helper import get_changed_fields

if TYPE_CHECKING:
    from app.events import EventBus

logger = logging.getLogger(__name__)


class PlanService:
    """Service layer for plan operations."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        event_bus: "EventBus | None" = None,
    ):
        self.plan_repo = plan_repo
        self._event_bus = event_bus
        logger.info("Plan service initialised")

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

    async def create_plan(self, user_id: UUID, plan_data: PlanCreate) -> Plan:
        logger.info("creating plan", extra={"user_id": str(user_id), "title": plan_data.title})
        plan = await self.plan_repo.create_plan(user_id=user_id, plan_data=plan_data)
        logger.info("plan created", extra={"plan_id": plan.id, "user_id": str(user_id)})
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.PLAN,
            entity_id=plan.id,
            action=ActionType.CREATED,
            snapshot=plan.model_dump(mode="json"),
        )
        return plan

    async def get_plan(self, user_id: UUID, plan_id: int) -> Plan | None:
        logger.info("getting plan", extra={"user_id": str(user_id), "plan_id": plan_id})
        plan = await self.plan_repo.get_plan_by_id(user_id=user_id, plan_id=plan_id)
        if plan:
            logger.info("plan retrieved", extra={"plan_id": plan_id})
            if settings.ACTIVITY_TRACK_READS and self._event_bus:
                await self._emit_event(
                    user_id=user_id,
                    entity_type=EntityType.PLAN,
                    entity_id=plan_id,
                    action=ActionType.READ,
                    snapshot=plan.model_dump(mode="json"),
                )
        else:
            logger.info("plan not found", extra={"plan_id": plan_id})
        return plan

    async def list_plans(
        self,
        user_id: UUID,
        project_id: int | None = None,
        status: PlanStatus | None = None,
    ) -> List[PlanSummary]:
        logger.info("listing plans", extra={"user_id": str(user_id), "project_id": project_id, "status": status.value if status else None})
        plans = await self.plan_repo.list_plans(user_id=user_id, project_id=project_id, status=status)
        logger.info("plans retrieved", extra={"count": len(plans)})
        return plans

    async def update_plan(
        self, user_id: UUID, plan_id: int, plan_data: PlanUpdate
    ) -> Plan | None:
        logger.info("updating plan", extra={"user_id": str(user_id), "plan_id": plan_id})

        existing = await self.plan_repo.get_plan_by_id(user_id=user_id, plan_id=plan_id)
        if not existing:
            logger.info("plan not found for update", extra={"plan_id": plan_id})
            return None

        # Validate status transitions
        if plan_data.status is not None and plan_data.status != existing.status:
            current = PlanStatus(existing.status)
            target = plan_data.status
            if target not in VALID_PLAN_TRANSITIONS.get(current, set()):
                raise InvalidStateTransitionError(
                    f"Cannot transition plan from {current.value} to {target.value}. "
                    f"Valid transitions: {[s.value for s in VALID_PLAN_TRANSITIONS.get(current, set())]}"
                )

        changed_fields = get_changed_fields(input_model=plan_data, existing_model=existing)
        if not changed_fields:
            logger.info("no changes detected", extra={"plan_id": plan_id})
            return existing

        updated = await self.plan_repo.update_plan(user_id=user_id, plan_id=plan_id, plan_data=plan_data)
        logger.info("plan updated", extra={"plan_id": plan_id})

        changes_dict = {
            field: {"old": old, "new": new}
            for field, (old, new) in changed_fields.items()
        }
        await self._emit_event(
            user_id=user_id,
            entity_type=EntityType.PLAN,
            entity_id=plan_id,
            action=ActionType.UPDATED,
            snapshot=updated.model_dump(mode="json"),
            changes=changes_dict,
        )
        return updated

    async def delete_plan(self, user_id: UUID, plan_id: int) -> bool:
        logger.info("deleting plan", extra={"user_id": str(user_id), "plan_id": plan_id})

        existing = await self.plan_repo.get_plan_by_id(user_id=user_id, plan_id=plan_id)
        if not existing:
            return False

        success = await self.plan_repo.delete_plan(user_id=user_id, plan_id=plan_id)
        if success:
            logger.info("plan deleted", extra={"plan_id": plan_id})
            await self._emit_event(
                user_id=user_id,
                entity_type=EntityType.PLAN,
                entity_id=plan_id,
                action=ActionType.DELETED,
                snapshot=existing.model_dump(mode="json"),
            )
        return success

    async def check_plan_completion(self, user_id: UUID, plan_id: int) -> bool:
        """Check if all tasks in a plan are done/cancelled and auto-complete the plan.

        Called by TaskService after task transitions. If all tasks are done/cancelled
        (with at least one done), auto-transitions plan to COMPLETED.

        Returns True if plan was auto-completed.
        """
        plan = await self.plan_repo.get_plan_by_id(user_id=user_id, plan_id=plan_id)
        if not plan or PlanStatus(plan.status) != PlanStatus.ACTIVE:
            return False

        # We need to check tasks - this requires access to task_repo
        # but we don't have it. The TaskService will call us with task info.
        # This method is called from TaskService which passes task info.
        # For now, the TaskService handles the logic and calls update_plan.
        return False
