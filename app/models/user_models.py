from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    external_id: str
    name: str
    email: str
    idp_metadata: dict | None = None
    notes: str | None = None

class UserUpdate(BaseModel):
    external_id: str | None = None
    name: str | None = None
    email: str | None = None
    idp_metadata: dict | None = None
    notes: str | None = None

class User(UserCreate):
    id: UUID = Field(default_factory=lambda: uuid4())
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC), frozen=True)

    model_config = ConfigDict(from_attributes=True)

class UserResponse(BaseModel):
    name: str
    notes: str | None = None
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
