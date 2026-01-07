"""add activity log table

Revision ID: 20260106_activity
Revises: 20260106_provenance
Create Date: 2026-01-06

Adds activity_log table for event-driven architecture (Issue #7).
Tracks entity lifecycle events (created, updated, deleted) and optionally
read/query operations when ACTIVITY_TRACK_READS is enabled.

The table stores:
- entity_type: memory, project, document, code_artifact, entity, link
- action: created, updated, deleted, read, queried
- changes: full diff for updates {field: {old: x, new: y}}
- snapshot: complete entity state at event time
- actor: who/what triggered the event (user, system, llm-maintenance)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '20260106_activity'
down_revision: Union[str, Sequence[str], None] = '20260106_provenance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_user_id_type():
    """Get appropriate user_id type based on database."""
    if settings.DATABASE == "Postgres":
        return postgresql.UUID(as_uuid=True)
    else:
        return sa.String(36)


def upgrade() -> None:
    """Create activity_log table for event tracking."""
    user_id_type = _get_user_id_type()

    op.create_table(
        'activity_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'user_id',
            user_id_type,
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
            index=True
        ),
        # Event identification
        sa.Column('entity_type', sa.String(50), nullable=False, index=True),
        sa.Column('entity_id', sa.Integer(), nullable=False, default=0, index=True),
        sa.Column('action', sa.String(20), nullable=False, index=True),
        # Event payload (JSON columns)
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        # Actor tracking
        sa.Column('actor', sa.String(50), nullable=False, default='user', index=True),
        sa.Column('actor_id', sa.String(255), nullable=True),
        # Additional context
        sa.Column('metadata', sa.JSON(), nullable=True),
        # Timestamp
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True
        ),
    )

    # Composite index for common query patterns
    op.create_index(
        'ix_activity_log_user_entity',
        'activity_log',
        ['user_id', 'entity_type', 'entity_id']
    )
    op.create_index(
        'ix_activity_log_user_created',
        'activity_log',
        ['user_id', 'created_at']
    )


def downgrade() -> None:
    """Drop activity_log table."""
    op.drop_index('ix_activity_log_user_created', table_name='activity_log')
    op.drop_index('ix_activity_log_user_entity', table_name='activity_log')
    op.drop_table('activity_log')
