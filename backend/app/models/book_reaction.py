import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

BookReactionType = Enum("like", "dislike", name="book_reaction_type", native_enum=False)


class BookReaction(Base):
    __tablename__ = "book_reactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    isbn: Mapped[str] = mapped_column(ForeignKey("books.isbn"), primary_key=True)
    reaction: Mapped[str] = mapped_column(BookReactionType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
