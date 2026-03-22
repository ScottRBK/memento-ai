"""add skills table with association tables

Revision ID: 20260321_skills
Revises: 20260315_files
Create Date: 2026-03-21

Adds skills table for procedural memory (Agent Skills standard),
plus association tables for linking skills to memories, files,
code artifacts, and documents.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.config.settings import settings

# revision identifiers, used by Alembic.
revision: str = "20260321_skills"
down_revision: str | Sequence[str] | None = "20260315_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_user_id_type():
    """Get appropriate user_id type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _get_tags_column():
    """Get appropriate tags column type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}")
    return sa.Column("tags", sa.JSON(), nullable=False, server_default="[]")


def _get_allowed_tools_column():
    """Get appropriate allowed_tools column type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return sa.Column("allowed_tools", postgresql.ARRAY(sa.String()), nullable=True)
    return sa.Column("allowed_tools", sa.JSON(), nullable=True)


def _get_metadata_column():
    """Get appropriate metadata column type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return sa.Column("skill_metadata", postgresql.JSONB(), nullable=True)
    return sa.Column("skill_metadata", sa.JSON(), nullable=True)


def upgrade() -> None:
    """Create skills table and association tables."""
    user_id_type = _get_user_id_type()
    tags_column = _get_tags_column()
    allowed_tools_column = _get_allowed_tools_column()
    metadata_column = _get_metadata_column()

    columns = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", user_id_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.String(1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("compatibility", sa.String(500), nullable=True),
        allowed_tools_column,
        metadata_column,
        tags_column,
        sa.Column("importance", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]

    # Add embedding column for Postgres only (SQLite uses vec_skills virtual table)
    if settings.DATABASE == "Postgres":
        from pgvector.sqlalchemy import Vector
        columns.append(sa.Column("embedding", Vector(settings.EMBEDDING_DIMENSIONS), nullable=False))

    op.create_table("skills", *columns)
    op.create_index("ix_skills_user_id", "skills", ["user_id"])
    op.create_index("ix_skills_project_id", "skills", ["project_id"])
    op.create_index("ix_skills_name", "skills", ["name"])
    op.create_index("ix_skills_importance", "skills", ["importance"])

    # GIN indexes for Postgres only
    if settings.DATABASE == "Postgres":
        op.create_index("ix_skills_tags", "skills", ["tags"], postgresql_using="gin")

    # Memory-Skill association table
    op.create_table(
        "memory_skill_association",
        sa.Column("memory_id", sa.Integer(), sa.ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
    )

    # Skill-File association table
    op.create_table(
        "skill_file_association",
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
    )

    # Skill-CodeArtifact association table
    op.create_table(
        "skill_code_artifact_association",
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("code_artifact_id", sa.Integer(), sa.ForeignKey("code_artifacts.id", ondelete="CASCADE"), primary_key=True),
    )

    # Skill-Document association table
    op.create_table(
        "skill_document_association",
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    """Drop skills and association tables in reverse order."""
    op.drop_table("skill_document_association")
    op.drop_table("skill_code_artifact_association")
    op.drop_table("skill_file_association")
    op.drop_table("memory_skill_association")

    if settings.DATABASE == "Postgres":
        op.drop_index("ix_skills_tags", table_name="skills")

    op.drop_index("ix_skills_importance", table_name="skills")
    op.drop_index("ix_skills_name", table_name="skills")
    op.drop_index("ix_skills_project_id", table_name="skills")
    op.drop_index("ix_skills_user_id", table_name="skills")
    op.drop_table("skills")
