"""create runs tables

Revision ID: 20260308_0010
Revises: 20260308_0009
Create Date: 2026-03-08 22:30:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260308_0010"
down_revision: str | None = "20260308_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("team_slug", sa.String(length=120), nullable=False),
        sa.Column("team_title", sa.String(length=255), nullable=False),
        sa.Column("runtime_target", sa.String(length=32), nullable=False),
        sa.Column("repo_owner", sa.String(length=255), nullable=False),
        sa.Column("repo_name", sa.String(length=255), nullable=False),
        sa.Column("repo_full_name", sa.String(length=511), nullable=False),
        sa.Column("base_branch", sa.String(length=255), nullable=False),
        sa.Column("working_branch", sa.String(length=255), nullable=True),
        sa.Column("issue_number", sa.Integer(), nullable=True),
        sa.Column("issue_title", sa.String(length=255), nullable=True),
        sa.Column("issue_url", sa.String(length=1000), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("task_text", sa.Text(), nullable=True),
        sa.Column("runtime_config_json", sa.JSON(), nullable=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("workspace_path", sa.String(length=2000), nullable=True),
        sa.Column("repo_path", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.String(length=1000), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runs_created_by"), "runs", ["created_by"], unique=False)
    op.create_index(op.f("ix_runs_team_id"), "runs", ["team_id"], unique=False)
    op.create_index(op.f("ix_runs_workspace_id"), "runs", ["workspace_id"], unique=False)

    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_run_events_run_id"), "run_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_events_event_type"), "run_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_run_events_event_type"), table_name="run_events")
    op.drop_index(op.f("ix_run_events_run_id"), table_name="run_events")
    op.drop_table("run_events")

    op.drop_index(op.f("ix_runs_workspace_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_team_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_created_by"), table_name="runs")
    op.drop_table("runs")
