"""lms lesson user state (note, exercise passed, last visit)

Revision ID: c20261007a01
Revises: b20261005a01
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c20261007a01"
down_revision = "b20261005a01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lms_lesson_user_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("exercise_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_correct", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["lesson_id"], ["lms_lessons.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_lesson_user_state_user_lesson"),
    )
    for column in ("user_id", "lesson_id", "visited_at"):
        op.create_index(f"ix_lms_lesson_user_state_{column}", "lms_lesson_user_state", [column])


def downgrade() -> None:
    for column in ("user_id", "lesson_id", "visited_at"):
        op.drop_index(f"ix_lms_lesson_user_state_{column}", table_name="lms_lesson_user_state")
    op.drop_table("lms_lesson_user_state")
