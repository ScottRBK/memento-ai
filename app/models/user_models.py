from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from uuid import uuid4, UUID

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
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True) 
    
    model_config = ConfigDict(from_attributes=True) 

class UserResponse(BaseModel):
    name: str
    notes: str | None = None
    updated_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)