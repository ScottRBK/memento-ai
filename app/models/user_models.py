from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Optional

class UserCreate(BaseModel):
    external_id: str
    name: str
    email: str
    idp_metadata: Optional[dict] = None
    notes: Optional[str] = None

class UserUpdate(BaseModel):
    external_id: Optional[str] = None 
    name: Optional[str] = None
    email: Optional[str] = None
    idp_metadata: Optional[dict] = None
    notes: Optional[str] = None

class User(UserCreate):
    id: UUID = Field(default_factory=lambda: uuid4()) 
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc), frozen=True) 
    
    model_config = ConfigDict(from_attributes=True) 