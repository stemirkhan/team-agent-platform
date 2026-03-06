"""create teams and team_items tables

Revision ID: 20260306_0002
Revises: 20260306_0001
Create Date: 2026-03-06 21:00:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_0002"
down_revision: str | None = "20260306_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_teams_slug"),
    )
    op.create_index(op.f("ix_teams_slug"), "teams", ["slug"], unique=False)

    op.create_table(
        "team_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("role_name", sa.String(length=120), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_items_agent_id"), "team_items", ["agent_id"], unique=False)
    op.create_index(op.f("ix_team_items_team_id"), "team_items", ["team_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_team_items_team_id"), table_name="team_items")
    op.drop_index(op.f("ix_team_items_agent_id"), table_name="team_items")
    op.drop_table("team_items")

    op.drop_index(op.f("ix_teams_slug"), table_name="teams")
    op.drop_table("teams")
