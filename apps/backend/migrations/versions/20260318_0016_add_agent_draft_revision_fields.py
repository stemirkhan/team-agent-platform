"""Add draft revision shadow fields for published agents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260318_0016"
down_revision: str | None = "20260316_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add draft shadow fields used for published-agent revisions."""
    op.add_column("agents", sa.Column("draft_title", sa.String(length=255), nullable=True))
    op.add_column("agents", sa.Column("draft_short_description", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("draft_full_description", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("draft_category", sa.String(length=120), nullable=True))
    op.add_column("agents", sa.Column("draft_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Drop draft shadow fields used for published-agent revisions."""
    op.drop_column("agents", "draft_updated_at")
    op.drop_column("agents", "draft_category")
    op.drop_column("agents", "draft_full_description")
    op.drop_column("agents", "draft_short_description")
    op.drop_column("agents", "draft_title")
