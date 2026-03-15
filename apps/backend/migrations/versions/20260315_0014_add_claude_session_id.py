"""Add claude_session_id to runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260315_0014"
down_revision: str | None = "20260315_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add Claude-specific backward-compatible session column."""
    op.add_column("runs", sa.Column("claude_session_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Drop Claude-specific backward-compatible session column."""
    op.drop_column("runs", "claude_session_id")
