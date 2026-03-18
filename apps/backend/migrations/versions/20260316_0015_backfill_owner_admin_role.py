"""Backfill one explicit admin owner for legacy installs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260316_0015"
down_revision: str | None = "20260315_0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LEGACY_PLATFORM_OWNER_EMAIL = "platform-owner@team-agent-platform.local"


def upgrade() -> None:
    """Promote one owner account to admin on installs created before owner bootstrap existed."""
    connection = op.get_bind()

    admin_count = int(
        connection.scalar(
            sa.text(
                """
                SELECT COUNT(*)
                FROM users
                WHERE is_active = true
                  AND role = :admin_role
                """
            ),
            {"admin_role": "admin"},
        )
        or 0
    )
    if admin_count > 0:
        return

    promoted = connection.execute(
        sa.text(
            """
            UPDATE users
            SET role = :admin_role
            WHERE id = (
                SELECT id
                FROM users
                WHERE is_active = true
                  AND email = :platform_owner_email
                ORDER BY created_at ASC, id ASC
                LIMIT 1
            )
            """
        ),
        {
            "admin_role": "admin",
            "platform_owner_email": _LEGACY_PLATFORM_OWNER_EMAIL,
        },
    )
    if (promoted.rowcount or 0) > 0:
        return

    connection.execute(
        sa.text(
            """
            UPDATE users
            SET role = :admin_role
            WHERE id = (
                SELECT id
                FROM users
                WHERE is_active = true
                ORDER BY created_at ASC, id ASC
                LIMIT 1
            )
            """
        ),
        {"admin_role": "admin"},
    )


def downgrade() -> None:
    """Do not attempt to infer the previous owner role state."""
    return None
