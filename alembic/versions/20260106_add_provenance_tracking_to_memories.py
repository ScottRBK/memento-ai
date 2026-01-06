"""add provenance tracking to memories

Revision ID: 20260106_provenance
Revises: 20251216143413
Create Date: 2026-01-06

Adds provenance tracking fields to the memories table:
- source_repo: Repository/project source (e.g., 'owner/repo')
- source_files: Files that informed this memory (JSON list of paths)
- source_url: URL to original source material
- confidence: Encoding confidence score (0.0-1.0)
- encoding_agent: Agent/process that created this memory
- encoding_version: Version of encoding process/prompt

All fields are optional (nullable) for backward compatibility.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '20260106_provenance'
down_revision: Union[str, Sequence[str], None] = '20251216143413'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add provenance tracking columns to memories table."""
    # Add source_repo column (Text, nullable)
    op.add_column(
        'memories',
        sa.Column('source_repo', sa.Text(), nullable=True)
    )

    # Add source_files column (JSON/ARRAY, nullable)
    if settings.DATABASE == "Postgres":
        op.add_column(
            'memories',
            sa.Column('source_files', postgresql.ARRAY(sa.String()), nullable=True)
        )
    elif settings.DATABASE == "SQLite":
        op.add_column(
            'memories',
            sa.Column('source_files', sa.JSON(), nullable=True)
        )
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE}")

    # Add source_url column (Text, nullable)
    op.add_column(
        'memories',
        sa.Column('source_url', sa.Text(), nullable=True)
    )

    # Add confidence column (Float, nullable)
    op.add_column(
        'memories',
        sa.Column('confidence', sa.Float(), nullable=True)
    )

    # Add encoding_agent column (Text, nullable)
    op.add_column(
        'memories',
        sa.Column('encoding_agent', sa.Text(), nullable=True)
    )

    # Add encoding_version column (Text, nullable)
    op.add_column(
        'memories',
        sa.Column('encoding_version', sa.Text(), nullable=True)
    )

    # Add index on confidence for filtering by reliability
    op.create_index('ix_memories_confidence', 'memories', ['confidence'])


def downgrade() -> None:
    """Remove provenance tracking columns from memories table."""
    # Drop the index first
    op.drop_index('ix_memories_confidence', table_name='memories')

    # Drop all provenance columns
    op.drop_column('memories', 'source_repo')
    op.drop_column('memories', 'source_files')
    op.drop_column('memories', 'source_url')
    op.drop_column('memories', 'confidence')
    op.drop_column('memories', 'encoding_agent')
    op.drop_column('memories', 'encoding_version')
