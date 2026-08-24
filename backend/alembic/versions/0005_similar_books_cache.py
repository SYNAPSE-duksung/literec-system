"""create similar_books_cache

Revision ID: 0005_similar_books_cache
Revises: 0004_review_axes
Create Date: 2026-08-24

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_similar_books_cache"
down_revision = "0004_review_axes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "similar_books_cache",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id"), primary_key=True),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("similar_books_cache")
