"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-28

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "auth_provider",
            sa.Enum("local", "kakao", name="auth_provider", native_enum=False),
            nullable=False,
            server_default="local",
        ),
        sa.Column("provider_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("auth_provider", "provider_id", name="uq_users_auth_provider_id"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("preferred_emotions", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("avoided_traits", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "books",
        sa.Column("isbn", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("publisher", sa.String(), nullable=False),
        sa.Column("cover_url", sa.String(), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "book_aspects",
        sa.Column("isbn", sa.String(), sa.ForeignKey("books.isbn"), primary_key=True),
        sa.Column("emotion_experience", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("liked_elements", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("disliked_elements", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("themes", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("reading_context", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("isbn", sa.String(), sa.ForeignKey("books.isbn"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "source",
            sa.Enum("llm_generated", "user", name="review_source", native_enum=False),
            nullable=False,
        ),
        sa.Column("persona", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("emotion_tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("liked_points", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("disliked_points", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dislike_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "review_reactions",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reviews.id"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column(
            "reaction",
            sa.Enum("like", "dislike", name="review_reaction_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "book_reactions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("isbn", sa.String(), sa.ForeignKey("books.isbn"), primary_key=True),
        sa.Column(
            "reaction",
            sa.Enum("like", "dislike", name="book_reaction_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("book_reactions")
    op.drop_table("review_reactions")
    op.drop_table("reviews")
    op.drop_table("book_aspects")
    op.drop_table("books")
    op.drop_table("user_profiles")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
