"""add aka to entities

Revision ID: 20251216143413
Revises: 0c7b964dd1e7
Create Date: 2025-12-16

Adds the 'aka' (also known as) column to the entities table.
This column stores alternative names/aliases for entities and is
included in entity search functionality.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '20251216143413'
down_revision: Union[str, Sequence[str], None] = '0c7b964dd1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add aka column to entities table."""
    if settings.DATABASE == "Postgres":
        # PostgreSQL: Use ARRAY type with empty array default
        op.add_column(
            'entities',
            sa.Column('aka', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}')
        )
        # Add GIN index for efficient array searches
        op.create_index('ix_entities_aka', 'entities', ['aka'], postgresql_using='gin')
    elif settings.DATABASE == "SQLite":
        # SQLite: Use JSON type with empty array default
        op.add_column(
            'entities',
            sa.Column('aka', sa.JSON(), nullable=False, server_default='[]')
        )
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE}")


def downgrade() -> None:
    """Remove aka column from entities table."""
    if settings.DATABASE == "Postgres":
        op.drop_index('ix_entities_aka', table_name='entities')

    op.drop_column('entities', 'aka')
