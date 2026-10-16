"""plan live records (placar ao vivo do plano, plan_live_v1)

Revision ID: e20261014a01
Revises: d20261013a01
Create Date: 2026-10-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e20261014a01"
down_revision = "d20261013a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_live_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset", sa.String(16), nullable=False),
        sa.Column("plan_date", sa.String(10), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop_distance", sa.Float(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rule_sha256", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("asset", "plan_date", "direction", name="uq_plan_live_record"),
    )
    op.create_index("ix_plan_live_records_asset", "plan_live_records", ["asset"])
    op.create_index("ix_plan_live_records_plan_date", "plan_live_records", ["plan_date"])
    op.create_index("ix_plan_live_records_closed", "plan_live_records", ["closed"])


def downgrade() -> None:
    op.drop_index("ix_plan_live_records_closed", table_name="plan_live_records")
    op.drop_index("ix_plan_live_records_plan_date", table_name="plan_live_records")
    op.drop_index("ix_plan_live_records_asset", table_name="plan_live_records")
    op.drop_table("plan_live_records")
