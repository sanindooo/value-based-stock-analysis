"""initial schema

Revision ID: 0d75e61f3e58
Revises: 
Create Date: 2026-05-15 22:59:06.389888
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0d75e61f3e58'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("ticker", sa.String(10), primary_key=True),
        sa.Column("company_name", sa.String(255)),
        sa.Column("sector", sa.String(100)),
        sa.Column("industry", sa.String(255)),
        sa.Column("market_cap", sa.Float),
        sa.Column("price", sa.Float),
        sa.Column("pe_ratio", sa.Float),
        sa.Column("forward_pe", sa.Float),
        sa.Column("peg_ratio", sa.Float),
        sa.Column("pb_ratio", sa.Float),
        sa.Column("ps_ratio", sa.Float),
        sa.Column("price_to_cash", sa.Float),
        sa.Column("price_to_fcf", sa.Float),
        sa.Column("eps_growth_this_year", sa.Float),
        sa.Column("eps_growth_next_year", sa.Float),
        sa.Column("eps_growth_past_5y", sa.Float),
        sa.Column("eps_growth_next_5y", sa.Float),
        sa.Column("sales_growth_past_5y", sa.Float),
        sa.Column("roe", sa.Float),
        sa.Column("roa", sa.Float),
        sa.Column("roi", sa.Float),
        sa.Column("gross_margin", sa.Float),
        sa.Column("operating_margin", sa.Float),
        sa.Column("net_profit_margin", sa.Float),
        sa.Column("dividend_yield", sa.Float),
        sa.Column("current_ratio", sa.Float),
        sa.Column("quick_ratio", sa.Float),
        sa.Column("debt_to_equity", sa.Float),
        sa.Column("lt_debt_to_equity", sa.Float),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "screening_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("filter_config", sa.JSON, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="pending"),
    )

    op.create_table(
        "screening_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "screening_run_id",
            sa.Integer,
            sa.ForeignKey("screening_runs.id"),
        ),
        sa.Column("stock_ticker", sa.String(10), sa.ForeignKey("stocks.ticker")),
        sa.Column("composite_score", sa.Float, server_default="0"),
        sa.Column("metric_snapshot", sa.JSON, server_default="{}"),
        sa.Column("conviction_data", sa.JSON, server_default="{}"),
        sa.Column("summary", sa.String(1000)),
        sa.Column("stage", sa.String(20), server_default="'screened'"),
    )

    op.create_table(
        "research_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("stock_ticker", sa.String(10)),
        sa.Column("report_content", sa.JSON, server_default="{}"),
        sa.Column("sources", sa.JSON, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "portfolio_preferences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("preferred_sectors", sa.JSON, server_default="[]"),
        sa.Column("risk_tolerance", sa.String(20), server_default="'moderate'"),
        sa.Column("hold_duration", sa.String(20), server_default="'3-5y'"),
        sa.Column("category_weights", sa.JSON, server_default='{"value":25,"growth":25,"financial_health":25,"profitability":25}'),
        sa.Column("metric_overrides", sa.JSON, server_default="{}"),
    )

    op.create_table(
        "task_status",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_type", sa.String(50)),
        sa.Column("status", sa.String(20), server_default="'pending'"),
        sa.Column("result_id", sa.Integer),
        sa.Column("progress", sa.String(50)),
        sa.Column("error_message", sa.String(1000)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("task_status")
    op.drop_table("portfolio_preferences")
    op.drop_table("research_reports")
    op.drop_table("screening_results")
    op.drop_table("screening_runs")
    op.drop_table("stocks")
