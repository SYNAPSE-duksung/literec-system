import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

RecommendationEventType = Enum(
    "impression", "click", "like", "review", name="recommendation_event_type", native_enum=False
)
RecommendationEventSource = Enum(
    "home", "book_detail", "review_detail", name="recommendation_event_source", native_enum=False
)


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id: Mapped[str] = mapped_column(String, ForeignKey("books.isbn"), nullable=False)
    event_type: Mapped[str] = mapped_column(RecommendationEventType, nullable=False)
    source: Mapped[str | None] = mapped_column(RecommendationEventSource, nullable=True)
    rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
