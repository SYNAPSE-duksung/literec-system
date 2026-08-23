"""create review_axes

Revision ID: 0004_review_axes
Revises: 0003_recommendation_events
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_review_axes"
down_revision = "0003_recommendation_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_axes",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id"), primary_key=True),
        sa.Column("emotion_experience", sa.Text(), nullable=True),
        sa.Column("liked_elements", sa.Text(), nullable=True),
        sa.Column("disliked_elements", sa.Text(), nullable=True),
        sa.Column("themes", sa.Text(), nullable=True),
        sa.Column("reading_context", sa.Text(), nullable=True),
        sa.Column("structured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_axes")
