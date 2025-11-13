"""
SQLAlchemy ORM Models for SQLite database

Key differences from Postgres tables:
- UUID stored as String (TEXT) instead of native UUID
- ARRAY columns stored as JSON strings
- JSONB becomes JSON
- Vector embeddings stored as TEXT for sqlite-vec
- No GIN or HNSW indexes (SQLite doesn't support these)
"""
from typing import List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Table,
    Boolean,
    Index,
    JSON,
    Float,
)
from uuid import uuid4
from datetime import datetime, timezone
from app.config.settings import settings


class Base(DeclarativeBase):
    """Base Class for all ORM models"""
    pass


# Association table for many-to-many relationship between memories and projects
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

# Association table for many-to-many relationship between memories and entities
memory_entity_association = Table(
    "memory_entity_association",
    Base.metadata,
    Column("memory_id", Integer, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("entity_id", Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True),
)


class UsersTable(Base):
    """
    User Table Model (SQLite)

    UUID stored as String (TEXT) for SQLite compatibility
    """
    __tablename__ = "users"

    # UUID as String in SQLite
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))

    # Metadata - JSONB becomes JSON
    idp_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    memories: Mapped[List["MemoryTable"]] = relationship(
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
    entities: Mapped[List["EntitiesTable"]] = relationship(
        "EntitiesTable",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class MemoryTable(Base):
    """
    Memory Table Model (SQLite)

    Key differences:
    - user_id as String (TEXT UUID)
    - keywords/tags as JSON (serialized arrays)
    - embedding as TEXT for sqlite-vec compatibility
    """

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Memory Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)

    # Arrays as JSON - repository layer handles serialization
    keywords: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False)

    # Metadata
    importance: Mapped[int] = mapped_column(Integer, nullable=False)

    # Vector embedding as TEXT for sqlite-vec
    # Will be serialized JSON array or binary format
    embedding: Mapped[str] = mapped_column(Text, nullable=False)

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
    entities: Mapped[List["EntitiesTable"]] = relationship(
        "EntitiesTable",
        secondary=memory_entity_association,
        back_populates="memories",
    )

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

    @property
    def linked_memory_ids(self) -> List[int]:
        """
        Compute linked memory IDs from bidirectional relationships.

        Combines IDs from both directions since links are bidirectional:
        - linked_memories: where this memory is the source
        - linking_memories: where this memory is the target

        Returns:
            List of linked memory IDs, or empty list if relationships not loaded
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import NO_VALUE

        insp = inspect(self)
        result = []

        if insp.attrs.linked_memories.loaded_value is not NO_VALUE:
            result.extend([m.id for m in self.linked_memories])

        if insp.attrs.linking_memories.loaded_value is not NO_VALUE:
            result.extend([m.id for m in self.linking_memories])

        return result

    @property
    def project_ids(self) -> List[int]:
        """
        Compute project IDs from projects relationship.

        Returns:
            List of project IDs, or empty list if relationship not loaded
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import NO_VALUE

        insp = inspect(self)
        if insp.attrs.projects.loaded_value is not NO_VALUE:
            return [p.id for p in self.projects]
        return []

    @property
    def code_artifact_ids(self) -> List[int]:
        """
        Compute code artifact IDs from code_artifacts relationship.

        Returns:
            List of code artifact IDs, or empty list if relationship not loaded
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import NO_VALUE

        insp = inspect(self)
        if insp.attrs.code_artifacts.loaded_value is not NO_VALUE:
            return [a.id for a in self.code_artifacts]
        return []

    @property
    def document_ids(self) -> List[int]:
        """
        Compute document IDs from documents relationship.

        Returns:
            List of document IDs, or empty list if relationship not loaded
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import NO_VALUE

        insp = inspect(self)
        if insp.attrs.documents.loaded_value is not NO_VALUE:
            return [d.id for d in self.documents]
        return []

    @property
    def entity_ids(self) -> List[int]:
        """
        Compute entity IDs from entities relationship.

        Returns:
            List of entity IDs, or empty list if relationship not loaded
        """
        from sqlalchemy import inspect
        from sqlalchemy.orm.attributes import NO_VALUE

        insp = inspect(self)
        if insp.attrs.entities.loaded_value is not NO_VALUE:
            return [e.id for e in self.entities]
        return []

    __table_args__ = (
        Index("ix_memories_user_id", "user_id"),
        Index("ix_memories_importance", "importance"),
        Index("ix_memories_is_obsolete", "is_obsolete"),
        Index("ix_memories_superseded_by", "superseded_by"),
        # Note: No GIN indexes for tags/keywords (Postgres-specific)
        # Note: No HNSW index for embedding (will use sqlite-vec functions)
    )


class MemoryLinkTable(Base):
    """
    Bidirectional links table for memories (SQLite)
    """
    __tablename__ = "memory_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Ensure unique bidirectional links
    __table_args__ = (
        Index("ix_memory_links_source_target", "source_id", "target_id", unique=True),
        Index("ix_memory_links_target_source", "target_id", "source_id"),
    )


class ProjectsTable(Base):
    """
    Project metadata for organizing memories (SQLite)
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Project information
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
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
    entities: Mapped[List["EntitiesTable"]] = relationship(
        "EntitiesTable",
        back_populates="project",
    )

    @hybrid_property
    def memory_count(self) -> int:
        """Return the count of memories linked to this project"""
        return len(self.memories)

    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_status", "status"),
    )


class CodeArtifactsTable(Base):
    """
    Table for maintaining artifacts (SQLite)

    Supports dual relationships:
    - Direct project link (project_id) for project-specific code
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "code_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # Code Artifact information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(100), nullable=False)

    # Tags as JSON array
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False)

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
        # Note: No GIN index for tags (Postgres-specific)
    )


class DocumentsTable(Base):
    """
    Table for storing text documents and long-form content referenced by memories (SQLite)

    Supports dual relationships:
    - Direct project link (project_id) for project-specific documents
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # Document information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), default="text", nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Tags as JSON array
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False)

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
        # Note: No GIN index for tags (Postgres-specific)
    )


class EntitiesTable(Base):
    """
    Table for storing entities (organizations, individuals, teams, devices, etc.) (SQLite)
    that can be referenced by memories and related to each other through relationships

    Supports dual relationships:
    - Direct project link (project_id) for project-specific entities
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # Entity information
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_type: Mapped[str] = mapped_column(String(100), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # Tags as JSON array
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False)

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
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="entities")
    project: Mapped["ProjectsTable"] = relationship("ProjectsTable", back_populates="entities")
    memories: Mapped[List["MemoryTable"]] = relationship(
        "MemoryTable",
        secondary=memory_entity_association,
        back_populates="entities",
    )

    # Entity relationships (as source)
    outgoing_relationships: Mapped[List["EntityRelationshipsTable"]] = relationship(
        "EntityRelationshipsTable",
        foreign_keys="EntityRelationshipsTable.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan"
    )

    # Entity relationships (as target)
    incoming_relationships: Mapped[List["EntityRelationshipsTable"]] = relationship(
        "EntityRelationshipsTable",
        foreign_keys="EntityRelationshipsTable.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_entities_user_id", "user_id"),
        Index("ix_entities_project_id", "project_id"),
        Index("ix_entities_entity_type", "entity_type"),
        Index("ix_entities_name", "name"),
        # Note: No GIN index for tags (Postgres-specific)
    )


class EntityRelationshipsTable(Base):
    """
    Table for storing relationships between entities (knowledge graph edges) (SQLite)

    Supports weighted, typed relationships with confidence scores and metadata
    for building a rich knowledge graph of entity connections.
    """
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationship endpoints
    source_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)

    # Relationship information
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)

    # Metadata as JSON
    relationship_metadata: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)

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
    source_entity: Mapped["EntitiesTable"] = relationship(
        "EntitiesTable",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships"
    )
    target_entity: Mapped["EntitiesTable"] = relationship(
        "EntitiesTable",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships"
    )

    __table_args__ = (
        Index("ix_entity_relationships_user_id", "user_id"),
        Index("ix_entity_relationships_source_entity_id", "source_entity_id"),
        Index("ix_entity_relationships_target_entity_id", "target_entity_id"),
        Index("ix_entity_relationships_relationship_type", "relationship_type"),
        # Unique constraint to prevent duplicate relationships
        Index("ix_entity_relationships_unique", "source_entity_id", "target_entity_id", "relationship_type", unique=True),
    )
