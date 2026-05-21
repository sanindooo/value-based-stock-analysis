"""add preservation and analysis tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-21 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("screening_results", sa.Column("preservation_score", sa.Float, nullable=True))
    op.add_column("portfolio_preferences", sa.Column("preservation_enabled", sa.Boolean, server_default="false", nullable=False))
    op.add_column("research_reports", sa.Column("mode", sa.String(20), server_default="value", nullable=False))
    op.execute("UPDATE research_reports SET mode='value' WHERE mode IS NULL")

    op.create_table(
        "stock_analysis",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("stock_ticker", sa.String(10), sa.ForeignKey("stocks.ticker"), nullable=False),
        sa.Column("screening_run_id", sa.Integer, sa.ForeignKey("screening_runs.id"), nullable=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="value"),
        sa.Column("analysis_data", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_stock_analysis_ticker", "stock_analysis", ["stock_ticker"])


def downgrade() -> None:
    op.drop_index("ix_stock_analysis_ticker", table_name="stock_analysis")
    op.drop_table("stock_analysis")
    op.drop_column("research_reports", "mode")
    op.drop_column("portfolio_preferences", "preservation_enabled")
    op.drop_column("screening_results", "preservation_score")
