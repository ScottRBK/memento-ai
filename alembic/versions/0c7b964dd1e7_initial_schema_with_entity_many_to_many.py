"""initial schema with entity many-to-many

Revision ID: 0c7b964dd1e7
Revises:
Create Date: 2025-11-21 01:11:16.235845

This migration delegates to database-specific helper modules:
- alembic/_db_helpers/db_postgres_impl.py for PostgreSQL
- alembic/_db_helpers/db_sqlite_impl.py for SQLite

Each helper contains database-specific type implementations.
"""
from typing import Sequence, Union
import importlib.util
from pathlib import Path

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '0c7b964dd1e7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _load_helper_module(module_name: str):
    """Load a helper module from the _db_helpers directory."""
    # Get the path to this file's directory
    current_dir = Path(__file__).parent
    # Navigate to the _db_helpers directory
    helpers_dir = current_dir.parent / "_db_helpers"
    module_path = helpers_dir / f"{module_name}.py"

    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade() -> None:
    """Upgrade schema - delegates to database-specific implementation."""
    if settings.DATABASE == "Postgres":
        module = _load_helper_module("db_postgres_impl")
        module.upgrade_postgres()
    elif settings.DATABASE == "SQLite":
        module = _load_helper_module("db_sqlite_impl")
        module.upgrade_sqlite()
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE}")


def downgrade() -> None:
    """Downgrade schema - delegates to database-specific implementation."""
    if settings.DATABASE == "Postgres":
        module = _load_helper_module("db_postgres_impl")
        module.downgrade_postgres()
    elif settings.DATABASE == "SQLite":
        module = _load_helper_module("db_sqlite_impl")
        module.downgrade_sqlite()
    else:
        raise ValueError(f"Unsupported database type: {settings.DATABASE}")
