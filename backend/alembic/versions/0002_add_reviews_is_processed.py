"""add reviews.is_processed

Revision ID: 0002_add_reviews_is_processed
Revises: 0001_initial_schema
Create Date: 2026-08-13

"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_reviews_is_processed"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_reviews_is_processed", "reviews", ["is_processed"])


def downgrade() -> None:
    op.drop_index("ix_reviews_is_processed", table_name="reviews")
    op.drop_column("reviews", "is_processed")
