"""create recommendation_events

Revision ID: 0003_recommendation_events
Revises: 0002_add_reviews_is_processed
Create Date: 2026-08-13

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_recommendation_events"
down_revision = "0002_add_reviews_is_processed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("book_id", sa.String(), sa.ForeignKey("books.isbn"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "impression", "click", "like", "review",
                name="recommendation_event_type", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "home", "book_detail", "review_detail",
                name="recommendation_event_source", native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rec_events_user_id", "recommendation_events", ["user_id"])
    op.create_index("ix_rec_events_created_at", "recommendation_events", ["created_at"])
    op.create_index("ix_rec_events_event_type", "recommendation_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("recommendation_events")
