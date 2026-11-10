"""macro intelligence history

Revision ID: 8c7d5b1e2a90
Revises: 4a326e2f07a9
Create Date: 2026-09-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8c7d5b1e2a90"
down_revision = "4a326e2f07a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_intelligence_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.String(length=10), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage_pct", sa.Float(), nullable=False),
        sa.Column("fresh_count", sa.Integer(), nullable=False),
        sa.Column("stale_count", sa.Integer(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("macro_intelligence_snapshots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_macro_intelligence_snapshots_captured_at"), ["captured_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_macro_intelligence_snapshots_snapshot_date"), ["snapshot_date"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("macro_intelligence_snapshots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_macro_intelligence_snapshots_snapshot_date"))
        batch_op.drop_index(batch_op.f("ix_macro_intelligence_snapshots_captured_at"))
    op.drop_table("macro_intelligence_snapshots")
