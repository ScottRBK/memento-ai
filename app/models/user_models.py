from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class UserInput(BaseModel):
    external_id: str
    name: str
    email: str
    identity_provider_metadata: dict

class User(UserInput):
    id: str = Field(default_factory=lambda: str(uuid4())) 
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True) 