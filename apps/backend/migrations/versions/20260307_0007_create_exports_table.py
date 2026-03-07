"""create exports table

Revision ID: 20260307_0007
Revises: 20260307_0006
Create Date: 2026-03-07 18:05:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260307_0007"
down_revision: str | None = "20260307_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("runtime_target", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_url", sa.String(length=1000), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exports_entity_type"), "exports", ["entity_type"], unique=False)
    op.create_index(op.f("ix_exports_entity_id"), "exports", ["entity_id"], unique=False)
    op.create_index(op.f("ix_exports_created_by"), "exports", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_exports_created_by"), table_name="exports")
    op.drop_index(op.f("ix_exports_entity_id"), table_name="exports")
    op.drop_index(op.f("ix_exports_entity_type"), table_name="exports")
    op.drop_table("exports")
