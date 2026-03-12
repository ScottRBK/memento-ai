"""add plans, tasks, criteria, and task_dependencies tables

Revision ID: 20260312_planning
Revises: 20260106_activity
Create Date: 2026-03-12

Adds plans, tasks, criteria, and task_dependencies tables for
structured procedural memory and multi-agent task coordination (Issue #28).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config.settings import settings


# revision identifiers, used by Alembic.
revision: str = '20260312_planning'
down_revision: Union[str, Sequence[str], None] = '20260106_activity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_user_id_type():
    """Get appropriate user_id type based on database."""
    if settings.DATABASE == "Postgres":
        from sqlalchemy.dialects import postgresql
        return postgresql.UUID(as_uuid=True)
    else:
        return sa.String(36)


def upgrade() -> None:
    """Create plans, tasks, criteria, and task_dependencies tables."""
    user_id_type = _get_user_id_type()

    # Plans table
    op.create_table(
        'plans',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', user_id_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_plans_user_id', 'plans', ['user_id'])
    op.create_index('ix_plans_project_id', 'plans', ['project_id'])
    op.create_index('ix_plans_status', 'plans', ['status'])

    # Tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', user_id_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.Integer(), sa.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('state', sa.String(20), nullable=False, server_default='todo'),
        sa.Column('priority', sa.String(5), nullable=False, server_default='P2'),
        sa.Column('assigned_agent', sa.String(200), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('ix_tasks_plan_id', 'tasks', ['plan_id'])
    op.create_index('ix_tasks_state', 'tasks', ['state'])
    op.create_index('ix_tasks_priority', 'tasks', ['priority'])
    op.create_index('ix_tasks_assigned_agent', 'tasks', ['assigned_agent'])

    # Criteria table
    op.create_table(
        'criteria',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', user_id_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('met', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('met_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_criteria_task_id', 'criteria', ['task_id'])
    op.create_index('ix_criteria_met', 'criteria', ['met'])

    # Task dependencies table
    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', user_id_type, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('depends_on_task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_task_deps_unique', 'task_dependencies', ['task_id', 'depends_on_task_id'], unique=True)


def downgrade() -> None:
    """Drop planning tables in reverse order."""
    op.drop_index('ix_task_deps_unique', table_name='task_dependencies')
    op.drop_table('task_dependencies')

    op.drop_index('ix_criteria_met', table_name='criteria')
    op.drop_index('ix_criteria_task_id', table_name='criteria')
    op.drop_table('criteria')

    op.drop_index('ix_tasks_assigned_agent', table_name='tasks')
    op.drop_index('ix_tasks_priority', table_name='tasks')
    op.drop_index('ix_tasks_state', table_name='tasks')
    op.drop_index('ix_tasks_plan_id', table_name='tasks')
    op.drop_index('ix_tasks_user_id', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('ix_plans_status', table_name='plans')
    op.drop_index('ix_plans_project_id', table_name='plans')
    op.drop_index('ix_plans_user_id', table_name='plans')
    op.drop_table('plans')
