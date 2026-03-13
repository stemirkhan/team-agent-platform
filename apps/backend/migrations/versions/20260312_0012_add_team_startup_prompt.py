"""add team startup prompt

Revision ID: 20260312_0012
Revises: 20260311_0011
Create Date: 2026-03-12 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260312_0012"
down_revision: str | None = "20260311_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("startup_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "startup_prompt")
