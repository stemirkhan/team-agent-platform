"""add author_id to agents and teams

Revision ID: 20260306_0004
Revises: 20260306_0003
Create Date: 2026-03-06 22:10:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_0004"
down_revision: str | None = "20260306_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("author_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_agents_author_id"), "agents", ["author_id"], unique=False)
    op.create_foreign_key(
        "fk_agents_author_id_users",
        "agents",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("teams", sa.Column("author_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_teams_author_id"), "teams", ["author_id"], unique=False)
    op.create_foreign_key(
        "fk_teams_author_id_users",
        "teams",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_teams_author_id_users", "teams", type_="foreignkey")
    op.drop_index(op.f("ix_teams_author_id"), table_name="teams")
    op.drop_column("teams", "author_id")

    op.drop_constraint("fk_agents_author_id_users", "agents", type_="foreignkey")
    op.drop_index(op.f("ix_agents_author_id"), table_name="agents")
    op.drop_column("agents", "author_id")
