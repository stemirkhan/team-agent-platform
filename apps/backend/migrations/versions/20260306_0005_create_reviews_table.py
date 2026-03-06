"""create reviews table

Revision ID: 20260306_0005
Revises: 20260306_0004
Create Date: 2026-03-06 23:20:00
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_0005"
down_revision: str | None = "20260306_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("works_as_expected", sa.Boolean(), nullable=False),
        sa.Column("outdated_flag", sa.Boolean(), nullable=False),
        sa.Column("unsafe_flag", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_reviews_user_entity"),
    )
    op.create_index(op.f("ix_reviews_user_id"), "reviews", ["user_id"], unique=False)
    op.create_index(op.f("ix_reviews_entity_type"), "reviews", ["entity_type"], unique=False)
    op.create_index(op.f("ix_reviews_entity_id"), "reviews", ["entity_id"], unique=False)
    op.create_index("ix_reviews_entity_type_entity_id", "reviews", ["entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reviews_entity_type_entity_id", table_name="reviews")
    op.drop_index(op.f("ix_reviews_entity_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_entity_type"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_user_id"), table_name="reviews")
    op.drop_table("reviews")
