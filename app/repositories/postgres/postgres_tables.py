"""
SQLAlchmey ORM Models for Postgres database
"""
from typing import List
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
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

# Association table for many-to-many relationship between memories and entities
memory_entity_association = Table(
    "memory_entity_association",
    Base.metadata,
    Column("memory_id", Integer, ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
    Column("entity_id", Integer, ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True),
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
    entities: Mapped[List["EntitiesTable"]] = relationship(
        "EntitiesTable",
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

        # Check if relationships are loaded to avoid lazy-loading in async context
        insp = inspect(self)
        result = []

        # Only access if already loaded (not NO_VALUE)
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
    entities: Mapped[List["EntitiesTable"]] = relationship(
        "EntitiesTable",
        back_populates="project",
    )

    # Computed properties for Pydantic conversion
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

class EntitiesTable(Base):
    """
    Table for storing entities (organizations, individuals, teams, devices, etc.)
    that can be referenced by memories and related to each other through relationships

    Supports dual relationships:
    - Direct project link (project_id) for project-specific entities
    - Memory references (many-to-many) for cross-project reuse
    """
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    # Entity information
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # Organization, Individual, Team, Device, Other
    custom_type: Mapped[str] = mapped_column(String(100), nullable=True)  # Used when entity_type is "Other"
    notes: Mapped[str] = mapped_column(Text, nullable=True)
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
    user: Mapped["UsersTable"] = relationship("UsersTable", back_populates="entities")
    project: Mapped["ProjectsTable"] = relationship("ProjectsTable")
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
        Index("ix_entities_tags", "tags", postgresql_using="gin"),
        Index("ix_entities_name", "name"),
    )


class EntityRelationshipsTable(Base):
    """
    Table for storing relationships between entities (knowledge graph edges)

    Supports weighted, typed relationships with confidence scores and metadata
    for building a rich knowledge graph of entity connections.
    """
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationship endpoints
    source_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)

    # Relationship information
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "works_at", "owns", "manages"
    strength: Mapped[float] = mapped_column(nullable=True)  # 0.0-1.0 relationship strength
    confidence: Mapped[float] = mapped_column(nullable=True)  # 0.0-1.0 confidence score
    relationship_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)  # Flexible metadata (source, verification date, etc.)

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

