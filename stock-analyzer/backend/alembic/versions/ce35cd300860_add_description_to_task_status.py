"""add_description_to_task_status

Revision ID: ce35cd300860
Revises: 0d75e61f3e58
Create Date: 2026-05-16 08:11:35.744763
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'ce35cd300860'
down_revision: Union[str, None] = '0d75e61f3e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('task_status', sa.Column('description', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('task_status', 'description')
