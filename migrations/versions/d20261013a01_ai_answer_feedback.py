"""ai answer feedback (gostei / não gostei + comentário)

Revision ID: d20261013a01
Revises: c20261007a01
Create Date: 2026-10-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d20261013a01"
down_revision = "c20261007a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_answer_logs", sa.Column("rating", sa.Integer(), nullable=True))
    op.add_column("ai_answer_logs", sa.Column("feedback_comment", sa.Text(), nullable=True))
    op.add_column("ai_answer_logs", sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_answer_logs", "feedback_at")
    op.drop_column("ai_answer_logs", "feedback_comment")
    op.drop_column("ai_answer_logs", "rating")
