"""pin team items to agent versions

Revision ID: 20260308_0009
Revises: 20260308_0008
Create Date: 2026-03-08 13:10:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260308_0009"
down_revision: str | None = "20260308_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team_items_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("role_name", sa.String(length=120), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_items_v2_team_id"), "team_items_v2", ["team_id"], unique=False)
    op.create_index(
        op.f("ix_team_items_v2_agent_version_id"),
        "team_items_v2",
        ["agent_version_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO team_items_v2 (id, team_id, agent_version_id, role_name, order_index, config_json, is_required)
            SELECT
              ti.id,
              ti.team_id,
              av.id,
              ti.role_name,
              ti.order_index,
              ti.config_json,
              ti.is_required
            FROM team_items ti
            JOIN LATERAL (
              SELECT av.id
              FROM agent_versions av
              WHERE av.agent_id = ti.agent_id
              ORDER BY av.is_latest DESC, av.published_at DESC
              LIMIT 1
            ) av ON TRUE
            """
        )
    )

    op.drop_index(op.f("ix_team_items_team_id"), table_name="team_items")
    op.drop_index(op.f("ix_team_items_agent_id"), table_name="team_items")
    op.drop_table("team_items")

    op.rename_table("team_items_v2", "team_items")
    op.drop_index(op.f("ix_team_items_v2_team_id"), table_name="team_items")
    op.drop_index(op.f("ix_team_items_v2_agent_version_id"), table_name="team_items")
    op.create_index(op.f("ix_team_items_team_id"), "team_items", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_items_agent_version_id"), "team_items", ["agent_version_id"], unique=False)


def downgrade() -> None:
    op.create_table(
        "team_items_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("role_name", sa.String(length=120), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_items_v2_team_id"), "team_items_v2", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_items_v2_agent_id"), "team_items_v2", ["agent_id"], unique=False)

    op.execute(
        sa.text(
            """
            INSERT INTO team_items_v2 (id, team_id, agent_id, role_name, order_index, config_json, is_required)
            SELECT
              ti.id,
              ti.team_id,
              av.agent_id,
              ti.role_name,
              ti.order_index,
              ti.config_json,
              ti.is_required
            FROM team_items ti
            JOIN agent_versions av ON av.id = ti.agent_version_id
            """
        )
    )

    op.drop_index(op.f("ix_team_items_team_id"), table_name="team_items")
    op.drop_index(op.f("ix_team_items_agent_version_id"), table_name="team_items")
    op.drop_table("team_items")

    op.rename_table("team_items_v2", "team_items")
    op.drop_index(op.f("ix_team_items_v2_team_id"), table_name="team_items")
    op.drop_index(op.f("ix_team_items_v2_agent_id"), table_name="team_items")
    op.create_index(op.f("ix_team_items_team_id"), "team_items", ["team_id"], unique=False)
    op.create_index(op.f("ix_team_items_agent_id"), "team_items", ["agent_id"], unique=False)
