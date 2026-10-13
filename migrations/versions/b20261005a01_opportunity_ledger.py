"""opportunity ledger, AI answer log, paper executions

Revision ID: b20261005a01
Revises: a10dab202610
Create Date: 2026-10-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b20261005a01"
down_revision = "a10dab202610"
branch_labels = None
depends_on = None

EVENT_INDEXES = ("opportunity_id", "setup", "symbol", "mode", "state", "event_at", "recorded_at")
AI_LOG_INDEXES = ("user_id", "grounding_ok", "created_at")
PAPER_INDEXES = ("user_id", "opportunity_id", "created_at")


def upgrade() -> None:
    op.create_table(
        "opportunity_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("opportunity_id", sa.String(length=160), nullable=False),
        sa.Column("setup", sa.String(length=64), nullable=False),
        sa.Column("setup_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=True),
        sa.Column("approval", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash"),
    )
    for column in EVENT_INDEXES:
        op.create_index(f"ix_opportunity_events_{column}", "opportunity_events", [column])

    op.create_table(
        "ai_answer_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("tools_hash", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("grounding_ok", sa.Boolean(), nullable=False),
        sa.Column("violations", sa.JSON(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in AI_LOG_INDEXES:
        op.create_index(f"ix_ai_answer_logs_{column}", "ai_answer_logs", [column])

    op.create_table(
        "paper_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("opportunity_id", sa.String(length=160), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("planned_entry", sa.Float(), nullable=True),
        sa.Column("executed_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("direction", sa.String(length=8), nullable=True),
        sa.Column("slippage", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in PAPER_INDEXES:
        op.create_index(f"ix_paper_executions_{column}", "paper_executions", [column])


def downgrade() -> None:
    for column in PAPER_INDEXES:
        op.drop_index(f"ix_paper_executions_{column}", table_name="paper_executions")
    op.drop_table("paper_executions")
    for column in AI_LOG_INDEXES:
        op.drop_index(f"ix_ai_answer_logs_{column}", table_name="ai_answer_logs")
    op.drop_table("ai_answer_logs")
    for column in EVENT_INDEXES:
        op.drop_index(f"ix_opportunity_events_{column}", table_name="opportunity_events")
    op.drop_table("opportunity_events")
