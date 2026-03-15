"""add runtime_session_id to runs

Revision ID: 20260315_0013
Revises: 20260312_0012
Create Date: 2026-03-15 15:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260315_0013"
down_revision = "20260312_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("runtime_session_id", sa.String(length=255), nullable=True))
    op.execute("UPDATE runs SET runtime_session_id = codex_session_id WHERE codex_session_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("runs", "runtime_session_id")
