"""
SQLAlchmey ORM Models for Postgres database
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import(
    Column,
    Integer, 
    String,
    Text, 
    DateTime,
    ForeignKey,
    Table,
    Boolean,
    Index,
    JSON
)
from pgvector.sqlalchemy import Vector 
from uuid import uuid4, UUID
from datetime import datetime, timezone



class Base(DeclarativeBase):
    """Base Class for all ORM models"""
    pass


class UsersTable(Base):
    """
    User Table Model 
    """
    __tablename__= "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    idp_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict) 
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)


    
    

