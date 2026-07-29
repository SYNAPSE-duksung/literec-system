import random
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Book, Review
from app.schemas.recommendation import RecommendationOut, SimilarReviewRecommendationOut

router = APIRouter(prefix="/api", tags=["recommendations"])

# UI_DESIGN_SPEC.md의 RADAR_TRAITS와 동일한 5개 값 — 실제 매칭 로직 없이 더미 표시용으로만 사용.
RADAR_TRAITS = ["잔잔함", "몰입감", "서정성", "현실성", "여운"]

HOOK_LINE_TEMPLATES = [
    "지금 기분에 잘 어울리는 한 권이에요",
    "요즘 관심사와 닿아 있는 이야기예요",
    "천천히 곱씹으며 읽기 좋은 책이에요",
]


@router.get("/recommendations", response_model=list[RecommendationOut])
def get_recommendations(
    n: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    """완전 랜덤 N권을 반환하는 더미 구현.

    실제 추천 로직(임베딩/클러스터링/XAI)은 ML 파트에서 별도로 진행 중이며,
    이 엔드포인트는 그 연동 전까지 사용하는 임시(dummy) 구현이다.
    """
    books = db.query(Book).all()
    sample = random.sample(books, k=min(n, len(books)))
    return [
        RecommendationOut(
            bookId=book.isbn,
            hookLine=random.choice(HOOK_LINE_TEMPLATES),
            matchedTrait=random.choice(RADAR_TRAITS),
            explanation=f"'{book.title}'을(를) 추천해요. (더미 추천 — ML 연동 전 임시 로직)",
        )
        for book in sample
    ]


@router.get("/reviews/{review_id}/similar-books", response_model=list[SimilarReviewRecommendationOut])
def get_similar_books_for_review(
    review_id: uuid.UUID,
    n: int = Query(default=3, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[SimilarReviewRecommendationOut]:
    """리뷰 상세의 '유사 리뷰 기반 책 추천' 더미 구현.

    완전 랜덤이며, UI_DESIGN_SPEC.md §6.8 규칙대로 원 리뷰가 속한 도서(isbn)는 결과에서 제외한다.
    """
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")

    candidates = db.query(Book).filter(Book.isbn != review.isbn).all()
    sample = random.sample(candidates, k=min(n, len(candidates)))
    return [
        SimilarReviewRecommendationOut(
            sourceReviewId=str(review_id),
            bookId=book.isbn,
            matchedReviewSnippet=f"'{book.title}'에 대한 다른 독자의 리뷰가 비슷한 정서를 담고 있어요. (더미)",
            similarityReason="정서 키워드가 비슷해요 (더미 — ML 연동 전 임시 로직)",
        )
        for book in sample
    ]
