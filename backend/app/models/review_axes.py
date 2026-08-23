import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReviewAxes(Base):
    __tablename__ = "review_axes"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id"), primary_key=True
    )
    emotion_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    liked_elements: Mapped[str | None] = mapped_column(Text, nullable=True)
    disliked_elements: Mapped[str | None] = mapped_column(Text, nullable=True)
    themes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reading_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
