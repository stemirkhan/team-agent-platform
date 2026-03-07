"""create agent versions table

Revision ID: 20260307_0006
Revises: 20260306_0005
Create Date: 2026-03-07 15:10:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260307_0006"
down_revision: str | None = "20260306_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=True),
        sa.Column("manifest_json", sa.JSON(), nullable=True),
        sa.Column("source_archive_url", sa.String(length=1000), nullable=True),
        sa.Column("compatibility_matrix", sa.JSON(), nullable=True),
        sa.Column("export_targets", sa.JSON(), nullable=True),
        sa.Column("install_instructions", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
    )
    op.create_index(op.f("ix_agent_versions_agent_id"), "agent_versions", ["agent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_versions_agent_id"), table_name="agent_versions")
    op.drop_table("agent_versions")
