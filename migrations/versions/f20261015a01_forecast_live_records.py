"""forecast live records (previsão do próximo pregão gravada antes, volfc_v1)

Revision ID: f20261015a01
Revises: e20261014a01
Create Date: 2026-10-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f20261015a01"
down_revision = "e20261014a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "forecast_live_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("asset", sa.String(16), nullable=False),
        sa.Column("target_date", sa.String(10), nullable=False),
        sa.Column("based_on", sa.String(10), nullable=False),
        sa.Column("expected_pct", sa.Float(), nullable=False),
        sa.Column("low80_pct", sa.Float(), nullable=False),
        sa.Column("high80_pct", sa.Float(), nullable=False),
        sa.Column("event", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "asset", "target_date", name="uq_forecast_live_record"),
    )
    op.create_index("ix_forecast_live_records_kind", "forecast_live_records", ["kind"])
    op.create_index("ix_forecast_live_records_asset", "forecast_live_records", ["asset"])
    op.create_index("ix_forecast_live_records_target_date", "forecast_live_records", ["target_date"])


def downgrade() -> None:
    op.drop_index("ix_forecast_live_records_target_date", table_name="forecast_live_records")
    op.drop_index("ix_forecast_live_records_asset", table_name="forecast_live_records")
    op.drop_index("ix_forecast_live_records_kind", table_name="forecast_live_records")
    op.drop_table("forecast_live_records")
