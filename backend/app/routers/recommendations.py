import random
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Book, Review, User
from app.schemas.recommendation import RecommendationOut, SimilarReviewRecommendationOut
from app.security import get_current_user
from app.services import book_service

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get("/recommendations", response_model=list[RecommendationOut])
async def get_recommendations(
    n: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    """ML 서버(/recommend)를 호출해 유저 프로필 기반 추천을 반환한다."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{settings.ml_server_url}/recommend",
                json={"user_id": str(current_user.id), "k": n},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ML 서버 연결 실패")

    recommended = resp.json()  # [{book_id, hook_line, matched_trait, explanation}, ...]
    if not recommended:
        # 온보딩 미완료 등으로 ML 프로필이 아직 없는 유저 — 빈 추천 목록 반환
        return []

    isbn_list = [item["book_id"] for item in recommended]
    books_by_isbn = {b.isbn: b for b in book_service.get_books_by_isbn(db, isbn_list)}

    return [
        RecommendationOut(
            bookId=item["book_id"],
            hookLine=item["hook_line"],
            matchedTrait=item["matched_trait"],
            explanation=item["explanation"],
        )
        for item in recommended
        if item["book_id"] in books_by_isbn  # ML이 반환한 isbn이 DB에 없으면(시드 불일치 등) 건너뜀
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
