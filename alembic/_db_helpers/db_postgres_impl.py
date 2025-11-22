"""
PostgreSQL-specific migration implementation for initial schema with entity many-to-many

This module contains PostgreSQL-specific types and operations:
- UUID native type
- JSONB for metadata
- ARRAY for lists (tags, keywords)
- Vector for embeddings
- GIN and HNSW indexes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from pgvector.sqlalchemy import Vector
from app.config.settings import settings


def upgrade_postgres() -> None:
    """PostgreSQL-specific upgrade implementation"""
    op.create_table('users',
    sa.Column('id', UUID(as_uuid=True), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('idp_metadata', JSONB, nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_external_id'), 'users', ['external_id'], unique=True)
    op.create_table('entities',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('entity_type', sa.String(length=100), nullable=False),
    sa.Column('custom_type', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('tags', ARRAY(sa.String()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'], unique=False)
    op.create_index('ix_entities_name', 'entities', ['name'], unique=False)
    op.create_index('ix_entities_user_id', 'entities', ['user_id'], unique=False)
    op.create_table('memories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('keywords', ARRAY(sa.String()), nullable=False),
    sa.Column('tags', ARRAY(sa.String()), nullable=False),
    sa.Column('importance', sa.Integer(), nullable=False),
    sa.Column('embedding', Vector(settings.EMBEDDING_DIMENSIONS), nullable=False),
    sa.Column('is_obsolete', sa.Boolean(), nullable=False),
    sa.Column('obsolete_reason', sa.Text(), nullable=True),
    sa.Column('superseded_by', sa.Integer(), nullable=True),
    sa.Column('obsoleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['superseded_by'], ['memories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memories_importance', 'memories', ['importance'], unique=False)
    op.create_index('ix_memories_is_obsolete', 'memories', ['is_obsolete'], unique=False)
    op.create_index('ix_memories_superseded_by', 'memories', ['superseded_by'], unique=False)
    op.create_index('ix_memories_user_id', 'memories', ['user_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('project_type', sa.String(length=50), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('repo_name', sa.String(length=255), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_status', 'projects', ['status'], unique=False)
    op.create_index('ix_projects_user_id', 'projects', ['user_id'], unique=False)
    op.create_table('code_artifacts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('language', sa.String(length=100), nullable=False),
    sa.Column('tags', ARRAY(sa.String()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_code_artifacts_language', 'code_artifacts', ['language'], unique=False)
    op.create_index('ix_code_artifacts_project_id', 'code_artifacts', ['project_id'], unique=False)
    op.create_index('ix_code_artifacts_user_id', 'code_artifacts', ['user_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('document_type', sa.String(length=100), nullable=True),
    sa.Column('filename', sa.String(length=500), nullable=True),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('tags', ARRAY(sa.String()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_document_type', 'documents', ['document_type'], unique=False)
    op.create_index('ix_documents_project_id', 'documents', ['project_id'], unique=False)
    op.create_index('ix_documents_user_id', 'documents', ['user_id'], unique=False)
    op.create_table('entity_project_association',
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('entity_id', 'project_id')
    )
    op.create_table('entity_relationships',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('source_entity_id', sa.Integer(), nullable=False),
    sa.Column('target_entity_id', sa.Integer(), nullable=False),
    sa.Column('relationship_type', sa.String(length=100), nullable=False),
    sa.Column('strength', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('relationship_metadata', JSONB, nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['source_entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entity_relationships_relationship_type', 'entity_relationships', ['relationship_type'], unique=False)
    op.create_index('ix_entity_relationships_source_entity_id', 'entity_relationships', ['source_entity_id'], unique=False)
    op.create_index('ix_entity_relationships_target_entity_id', 'entity_relationships', ['target_entity_id'], unique=False)
    op.create_index('ix_entity_relationships_unique', 'entity_relationships', ['source_entity_id', 'target_entity_id', 'relationship_type'], unique=True)
    op.create_index('ix_entity_relationships_user_id', 'entity_relationships', ['user_id'], unique=False)
    op.create_table('memory_entity_association',
    sa.Column('memory_id', sa.Integer(), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('memory_id', 'entity_id')
    )
    op.create_table('memory_links',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', UUID(as_uuid=True), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['memories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_id'], ['memories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memory_links_source_target', 'memory_links', ['source_id', 'target_id'], unique=True)
    op.create_index('ix_memory_links_target_source', 'memory_links', ['target_id', 'source_id'], unique=False)
    op.create_table('memory_project_association',
    sa.Column('memory_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('memory_id', 'project_id')
    )
    op.create_table('memory_code_artifact_association',
    sa.Column('memory_id', sa.Integer(), nullable=False),
    sa.Column('code_artifact_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['code_artifact_id'], ['code_artifacts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('memory_id', 'code_artifact_id')
    )
    op.create_table('memory_document_association',
    sa.Column('memory_id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['memory_id'], ['memories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('memory_id', 'document_id')
    )


def downgrade_postgres() -> None:
    """PostgreSQL-specific downgrade implementation"""
    op.drop_table('memory_document_association')
    op.drop_table('memory_code_artifact_association')
    op.drop_table('memory_project_association')
    op.drop_index('ix_memory_links_target_source', table_name='memory_links')
    op.drop_index('ix_memory_links_source_target', table_name='memory_links')
    op.drop_table('memory_links')
    op.drop_table('memory_entity_association')
    op.drop_index('ix_entity_relationships_user_id', table_name='entity_relationships')
    op.drop_index('ix_entity_relationships_unique', table_name='entity_relationships')
    op.drop_index('ix_entity_relationships_target_entity_id', table_name='entity_relationships')
    op.drop_index('ix_entity_relationships_source_entity_id', table_name='entity_relationships')
    op.drop_index('ix_entity_relationships_relationship_type', table_name='entity_relationships')
    op.drop_table('entity_relationships')
    op.drop_table('entity_project_association')
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_index('ix_documents_project_id', table_name='documents')
    op.drop_index('ix_documents_document_type', table_name='documents')
    op.drop_table('documents')
    op.drop_index('ix_code_artifacts_user_id', table_name='code_artifacts')
    op.drop_index('ix_code_artifacts_project_id', table_name='code_artifacts')
    op.drop_index('ix_code_artifacts_language', table_name='code_artifacts')
    op.drop_table('code_artifacts')
    op.drop_index('ix_projects_user_id', table_name='projects')
    op.drop_index('ix_projects_status', table_name='projects')
    op.drop_table('projects')
    op.drop_index('ix_memories_user_id', table_name='memories')
    op.drop_index('ix_memories_superseded_by', table_name='memories')
    op.drop_index('ix_memories_is_obsolete', table_name='memories')
    op.drop_index('ix_memories_importance', table_name='memories')
    op.drop_table('memories')
    op.drop_index('ix_entities_user_id', table_name='entities')
    op.drop_index('ix_entities_name', table_name='entities')
    op.drop_index('ix_entities_entity_type', table_name='entities')
    op.drop_table('entities')
    op.drop_index(op.f('ix_users_external_id'), table_name='users')
    op.drop_table('users')
