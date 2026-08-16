from typing import Literal

from pydantic import BaseModel


class RecommendationEventCreate(BaseModel):
    book_id: str  # books.isbn
    event_type: Literal["impression", "click", "like", "review"]
    source: Literal["home", "book_detail", "review_detail"] | None = None
    rank: int | None = None  # impression일 때만 사용
