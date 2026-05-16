"""add progress_data to task_status and task_id to screening_runs

Revision ID: a1b2c3d4e5f6
Revises: ce35cd300860
Create Date: 2026-05-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ce35cd300860'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_status', sa.Column('progress_data', sa.JSON(), nullable=True))
    op.add_column(
        'screening_runs',
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('task_status.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('screening_runs', 'task_id')
    op.drop_column('task_status', 'progress_data')
