"""
SQLAlchmey ORM Models for Postgres database
"""
from typing import List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
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
)
from pgvector.sqlalchemy import Vector 
from uuid import uuid4, UUID
from datetime import datetime, timezone
from app.config.settings import settings



class Base(DeclarativeBase):
    """Base Class for all ORM models"""
    pass

memory_project_association = Table(
    "memory_project_association",
    Base.metadata,
    Column("memory_id", Integer, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for many-to-many relationship between memories and code artifacts
memory_code_artifact_association = Table(
    "memory_code_artifact_association",
    Base.metadata,
    Column("memory_id", Integer, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("code_artifact_id", Integer, ForeignKey("code_artifacts.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for many-to-many relationship between memories and documents
memory_document_association = Table(
    "memory_document_association",
    Base.metadata,
    Column("memory_id", Integer, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
)

class UsersTable(Base):
    """
    User Table Model 
    """
    __tablename__= "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    
    # Meta Data
    idp_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict) 
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False)

    # Relationships
    memories:   Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    projects: Mapped[List["ProjectsTable"]] = relationship(
        "ProjectsTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    code_artifacts: Mapped[List["CodeArtifactsTable"]] = relationship(
        "CodeArtifactsTable",
        back_populates="user",
        cascade="all, delete-orphan"
    ) 
    documents: Mapped[List["DocumentsTable"]] = relationship(
        "DocumentsTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )      

class MemoryTable(Base):
    """
    Memory Table Model
    """
    
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Memory Content 
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)

   # Meta Data
    importance: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[Vector] = mapped_column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=False)

    # Lifecycle Management
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    obsolete_reason: Mapped[str] = mapped_column(Text, nullable=True)
    superseded_by: Mapped[int] = mapped_column(Integer, ForeignKey("memories.id", ondelete="SET NULL"), nullable=True)
    obsoleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="memories")  
    projects: Mapped[List["ProjectsTable"]] = relationship(
        "ProjectsTable",
        secondary=memory_project_association,
        back_populates="memories",
    )
    code_artifacts: Mapped[List["CodeArtifactsTable"]] = relationship(
        "CodeArtifactsTable",
        secondary=memory_code_artifact_association,
        back_populates="memories",
    )
    documents: Mapped[List["DocumentsTable"]] = relationship(
        "DocumentsTable",
        secondary=memory_document_association,
        back_populates="memories",
    )
    
    # Self-referential relationship for memory links (many-to-many)
    linked_memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary="memory_links",
        primaryjoin="MemoryTable.id==MemoryLinkTable.source_id",
        secondaryjoin="MemoryTable.id==MemoryLinkTable.target_id",
        back_populates="linking_memories"
    )
    
    linking_memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary="memory_links",
        primaryjoin="MemoryTable.id==MemoryLinkTable.target_id",
        secondaryjoin="MemoryTable.id==MemoryLinkTable.source_id",
        back_populates="linked_memories",
        viewonly=True
    )
    
    __table_args__ = (
        Index("ix_memories_user_id", "user_id"),
        Index("ix_memories_importance", "importance"),
        Index("ix_memories_tags", "tags", postgresql_using="gin"),
        Index("ix_memories_keywords", "keywords", postgresql_using="gin"),
        Index("ix_memories_embedding", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_memories_is_obsolete", "is_obsolete"),
        Index("ix_memories_superseded_by", "superseded_by"),
    )
    
class MemoryLinkTable(Base):
    """
    Bidirectional links table for memories
    """
    __tablename__ = "memory_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Ensure unique bidirectional links (prevent duplicates)
    __table_args__ = (
        Index("ix_memory_links_source_target", "source_id", "target_id", unique=True),
        Index("ix_memory_links_target_source", "target_id", "source_id"),
    )

class ProjectsTable(Base):
    """
    Project meta data for organising memories
    """
    
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Project information
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=True) # TODO: create a proper enum for this
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False) # TODO: create a proper enum for this
    repo_name: Mapped[str] = mapped_column(String(255), nullable=True) 
    notes: Mapped[str] = mapped_column(Text, nullable=True)
       
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="projects")
    memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary=memory_project_association,
        back_populates="projects",
    )
    code_artifacts: Mapped[List["CodeArtifactsTable"]] = relationship(
        "CodeArtifactsTable",
        back_populates="project",
    )
    documents: Mapped[List["DocumentsTable"]] = relationship(
        "DocumentsTable",
        back_populates="project",
    )

    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_status", "status"),
    )
    
class CodeArtifactsTable(Base):
    """
    Table for maintaining artifacts

    Supports dual relationships:
    - Direct project link (project_id) for project-specific code
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "code_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # Code Artifact information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="code_artifacts")
    project: Mapped["ProjectsTable"] = relationship("ProjectsTable", back_populates="code_artifacts")
    memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary=memory_code_artifact_association,
        back_populates="code_artifacts",
    )

    __table_args__ = (
        Index("ix_code_artifacts_user_id", "user_id"),
        Index("ix_code_artifacts_project_id", "project_id"),
        Index("ix_code_artifacts_language", "language"),
        Index("ix_code_artifacts_tags", "tags", postgresql_using="gin"),
    )
    
class DocumentsTable(Base):
    """
    Table for storing text documents and long-form content referenced by memories

    Supports dual relationships:
    - Direct project link (project_id) for project-specific documents
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    
    # Document information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), default="text", nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
     # Relationships
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="documents")
    project: Mapped["ProjectsTable"] = relationship("ProjectsTable", back_populates="documents")
    memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary=memory_document_association,
        back_populates="documents",
    )

    __table_args__ = (
       Index("ix_documents_user_id", "user_id"),
       Index("ix_documents_project_id", "project_id"),
       Index("ix_documents_document_type", "document_type"),
       Index("ix_documents_tags", "tags", postgresql_using="gin"),
    )
    
    