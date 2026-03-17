"""add files table with memory and entity associations

Revision ID: 20260315_files
Revises: 20260312_planning
Create Date: 2026-03-15

Adds files table for binary content storage (images, PDFs, fonts, etc.),
memory_file_association and entity_file_association tables for linking
files to memories and entities (Issue #29).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '20260315_files'
down_revision: Union[str, Sequence[str], None] = '20260312_planning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_user_id_type():
    """Get appropriate user_id type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return postgresql.UUID(as_uuid=True)
    else:
        return sa.String(36)


def _get_tags_column():
    """Get appropriate tags column type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}')
    else:
        return sa.Column('tags', sa.JSON(), nullable=False, server_default='[]')


def upgrade() -> None:
    """Create files table and association tables."""
    user_id_type = _get_user_id_type()
    tags_column = _get_tags_column()

    # Files table
    op.create_table(
        'files',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', user_id_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('mime_type', sa.String(255), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        tags_column,
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_files_user_id', 'files', ['user_id'])
    op.create_index('ix_files_project_id', 'files', ['project_id'])
    op.create_index('ix_files_mime_type', 'files', ['mime_type'])

    # GIN index on tags for Postgres only
    if settings.DATABASE == "Postgres":
        op.create_index('ix_files_tags', 'files', ['tags'], postgresql_using='gin')

    # Memory-File association table
    op.create_table(
        'memory_file_association',
        sa.Column('memory_id', sa.Integer(), sa.ForeignKey('memories.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), primary_key=True),
    )

    # Entity-File association table
    op.create_table(
        'entity_file_association',
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.id', ondelete='CASCADE'), primary_key=True),
    )


def downgrade() -> None:
    """Drop files and association tables in reverse order."""
    op.drop_table('entity_file_association')
    op.drop_table('memory_file_association')

    if settings.DATABASE == "Postgres":
        op.drop_index('ix_files_tags', table_name='files')

    op.drop_index('ix_files_mime_type', table_name='files')
    op.drop_index('ix_files_project_id', table_name='files')
    op.drop_index('ix_files_user_id', table_name='files')
    op.drop_table('files')
