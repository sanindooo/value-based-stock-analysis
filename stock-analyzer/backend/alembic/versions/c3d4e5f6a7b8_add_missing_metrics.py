"""add missing canonical metrics to stocks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-16 12:02:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stocks', sa.Column('website', sa.String(500), nullable=True))
    op.add_column('stocks', sa.Column('beta', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('book_value_per_share', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('debt_to_ebitda', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('dividend_payout', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('projected_earnings_growth', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('analyst_rating', sa.Float(), nullable=True))
    op.add_column('stocks', sa.Column('trading_range_12m', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('stocks', 'trading_range_12m')
    op.drop_column('stocks', 'analyst_rating')
    op.drop_column('stocks', 'projected_earnings_growth')
    op.drop_column('stocks', 'dividend_payout')
    op.drop_column('stocks', 'debt_to_ebitda')
    op.drop_column('stocks', 'book_value_per_share')
    op.drop_column('stocks', 'beta')
    op.drop_column('stocks', 'website')
