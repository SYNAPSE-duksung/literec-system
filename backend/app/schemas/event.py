from typing import Literal

from pydantic import BaseModel


class RecommendationEventCreate(BaseModel):
    book_id: str  # books.isbn
    event_type: Literal["impression", "click", "like", "review"]
    source: Literal["home", "book_detail", "review_detail"] | None = None
    # 노출 순위. 원래 impression 전용으로 문서화됐지만 실제로는 클릭 이벤트도
    # 같은 rank를 함께 보내(순위별 CTR 분석 등에 필요) 특정 event_type으로 제한하지 않는다.
    rank: int | None = None
