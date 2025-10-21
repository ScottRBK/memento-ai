from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4, UUID


class UserWrite(BaseModel):
    external_id: str
    name: str
    email: str
    idp_metadata: dict
    notes: str 

class User(UserWrite):
    id: UUID = Field(default_factory=lambda: uuid4()) 
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True) 