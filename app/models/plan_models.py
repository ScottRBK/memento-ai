"""
Models for Plans, Tasks, Acceptance Criteria, and Task Dependencies.

These are tightly coupled aggregates forming the hierarchy:
    Project ← Plan ← Task ← Criterion
    Task ← TaskDependency → Task
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.settings import settings


# ============================================================================
# Enums
# ============================================================================


class PlanStatus(str, Enum):
    """Plan lifecycle states."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskState(str, Enum):
    """Task state machine states."""
    TODO = "todo"
    DOING = "doing"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task priority levels."""
    P0 = "P0"  # Critical
    P1 = "P1"  # High
    P2 = "P2"  # Medium
    P3 = "P3"  # Low


# ============================================================================
# State Machine Transitions
# ============================================================================


VALID_TASK_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.TODO:      {TaskState.DOING, TaskState.WAITING, TaskState.CANCELLED},
    TaskState.DOING:     {TaskState.DONE, TaskState.WAITING, TaskState.TODO, TaskState.CANCELLED},
    TaskState.WAITING:   {TaskState.TODO, TaskState.DOING, TaskState.CANCELLED},
    TaskState.DONE:      {TaskState.TODO},       # Reopen only
    TaskState.CANCELLED: {TaskState.TODO},        # Reinstate only
}

VALID_PLAN_TRANSITIONS: dict[PlanStatus, set[PlanStatus]] = {
    PlanStatus.DRAFT:     {PlanStatus.ACTIVE, PlanStatus.ARCHIVED},
    PlanStatus.ACTIVE:    {PlanStatus.COMPLETED, PlanStatus.ARCHIVED},
    PlanStatus.COMPLETED: {PlanStatus.ACTIVE},    # Reopen
    PlanStatus.ARCHIVED:  {PlanStatus.ACTIVE},    # Unarchive
}


# ============================================================================
# Criterion Models
# ============================================================================


class CriterionCreate(BaseModel):
    """Input model for creating an acceptance criterion."""
    description: str = Field(..., max_length=settings.CRITERION_DESCRIPTION_MAX_LENGTH)

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        return v.strip()


class CriterionUpdate(BaseModel):
    """PATCH model for updating a criterion."""
    description: Optional[str] = Field(None, max_length=settings.CRITERION_DESCRIPTION_MAX_LENGTH)
    met: Optional[bool] = None

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class Criterion(BaseModel):
    """Full criterion model returned from repository."""
    id: int
    task_id: int
    description: str
    met: bool = False
    met_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Task Dependency Models
# ============================================================================


class TaskDependencyCreate(BaseModel):
    """Input model for adding a dependency."""
    task_id: int
    depends_on_task_id: int

    @field_validator("depends_on_task_id")
    @classmethod
    def cannot_depend_on_self(cls, v: int, info) -> int:
        if info.data.get("task_id") == v:
            raise ValueError("A task cannot depend on itself")
        return v


class TaskDependency(BaseModel):
    """Full dependency model returned from repository."""
    id: int
    task_id: int
    depends_on_task_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Plan Models
# ============================================================================


class PlanCreate(BaseModel):
    """Input model for creating a plan."""
    title: str = Field(..., max_length=settings.PLAN_TITLE_MAX_LENGTH)
    project_id: int
    goal: Optional[str] = Field(None, max_length=settings.PLAN_GOAL_MAX_LENGTH)
    context: Optional[str] = Field(None, max_length=settings.PLAN_CONTEXT_MAX_LENGTH)
    status: PlanStatus = PlanStatus.DRAFT

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("goal", "context")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class PlanUpdate(BaseModel):
    """PATCH model for updating a plan."""
    title: Optional[str] = Field(None, max_length=settings.PLAN_TITLE_MAX_LENGTH)
    goal: Optional[str] = Field(None, max_length=settings.PLAN_GOAL_MAX_LENGTH)
    context: Optional[str] = Field(None, max_length=settings.PLAN_CONTEXT_MAX_LENGTH)
    status: Optional[PlanStatus] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("goal", "context")
    @classmethod
    def strip_optional(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class Plan(PlanCreate):
    """Full plan model returned from repository."""
    id: int
    user_id: str
    task_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanSummary(BaseModel):
    """Lightweight plan model for list operations."""
    id: int
    title: str
    project_id: int
    status: PlanStatus
    task_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Task Models
# ============================================================================


class TaskCreate(BaseModel):
    """Input model for creating a task."""
    title: str = Field(..., max_length=settings.TASK_TITLE_MAX_LENGTH)
    plan_id: int
    description: Optional[str] = Field(None, max_length=settings.TASK_DESCRIPTION_MAX_LENGTH)
    priority: TaskPriority = TaskPriority.P2
    assigned_agent: Optional[str] = Field(None, max_length=settings.TASK_AGENT_MAX_LENGTH)
    criteria: Optional[List[CriterionCreate]] = None
    dependency_ids: Optional[List[int]] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class TaskUpdate(BaseModel):
    """PATCH model for updating task metadata. State changes go through transition_task."""
    title: Optional[str] = Field(None, max_length=settings.TASK_TITLE_MAX_LENGTH)
    description: Optional[str] = Field(None, max_length=settings.TASK_DESCRIPTION_MAX_LENGTH)
    priority: Optional[TaskPriority] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class Task(BaseModel):
    """Full task model returned from repository."""
    id: int
    plan_id: int
    title: str
    description: Optional[str] = None
    state: TaskState = TaskState.TODO
    priority: TaskPriority = TaskPriority.P2
    assigned_agent: Optional[str] = None
    version: int = 1
    criteria: List[Criterion] = Field(default_factory=list)
    dependency_ids: List[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskSummary(BaseModel):
    """Lightweight task model for list operations."""
    id: int
    title: str
    plan_id: int
    state: TaskState
    priority: TaskPriority
    assigned_agent: Optional[str] = None
    version: int = 1
    criteria_met: int = 0
    criteria_total: int = 0
    blocked: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
