"""add run resume fields

Revision ID: 20260311_0011
Revises: 20260308_0010
Create Date: 2026-03-11 23:40:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260311_0011"
down_revision: str | None = "20260308_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("codex_session_id", sa.String(length=255), nullable=True))
    op.add_column("runs", sa.Column("transport_kind", sa.String(length=32), nullable=True))
    op.add_column("runs", sa.Column("transport_ref", sa.String(length=255), nullable=True))
    op.add_column(
        "runs",
        sa.Column(
            "resume_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("runs", sa.Column("interrupted_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("runs", "resume_attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_column("runs", "interrupted_at")
    op.drop_column("runs", "resume_attempt_count")
    op.drop_column("runs", "transport_ref")
    op.drop_column("runs", "transport_kind")
    op.drop_column("runs", "codex_session_id")
