"""signal records ('Avaliar um sinal' e placar da fonte)

Revision ID: g20261016a01
Revises: f20261015a01
Create Date: 2026-10-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g20261016a01"
down_revision = "f20261015a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("asset", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("entry", sa.Float(), nullable=False),
        sa.Column("stop", sa.Float(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("stop_distance", sa.Float(), nullable=False),
        sa.Column("target_distances", sa.JSON(), nullable=False),
        sa.Column("base_p", sa.JSON(), nullable=False),
        sa.Column("base_mean_r", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("result_r", sa.JSON(), nullable=False),
        sa.Column("ref_entry", sa.Float(), nullable=True),
        sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_signal_records_user_id", "signal_records", ["user_id"])
    op.create_index("ix_signal_records_source", "signal_records", ["source"])
    op.create_index("ix_signal_records_closed", "signal_records", ["closed"])
    op.create_index("ix_signal_records_created_at", "signal_records", ["created_at"])


def downgrade() -> None:
    for name in ("ix_signal_records_created_at", "ix_signal_records_closed", "ix_signal_records_source", "ix_signal_records_user_id"):
        op.drop_index(name, table_name="signal_records")
    op.drop_table("signal_records")
