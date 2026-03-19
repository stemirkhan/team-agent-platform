"""Create singleton platform settings table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260319_0017"
down_revision: str | None = "20260318_0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the singleton platform settings table."""
    op.create_table(
        "platform_settings",
        sa.Column("singleton_key", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("allow_open_registration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Drop the singleton platform settings table."""
    op.drop_table("platform_settings")
