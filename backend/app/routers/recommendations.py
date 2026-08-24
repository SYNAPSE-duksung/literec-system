import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Review, SimilarBooksCache, User
from app.schemas.recommendation import RecommendationOut, SimilarReviewRecommendationOut
from app.security import get_current_user
from app.services import book_service

router = APIRouter(prefix="/api", tags=["recommendations"])

# 캐시된 유사 리뷰 결과의 유효 기간 — 카탈로그가 주간 재계산(weekly-rebuild CronJob)되므로
# 그 주기에 맞춰 캐시도 자연스럽게 갱신되게 한다.
SIMILAR_BOOKS_CACHE_TTL = timedelta(days=7)


def _save_similar_books_cache(db: Session, review_id: uuid.UUID, results: list[dict]) -> None:
    row = db.get(SimilarBooksCache, review_id)
    if row is None:
        row = SimilarBooksCache(review_id=review_id)
        db.add(row)
    row.results = results
    row.computed_at = datetime.now(timezone.utc)
    db.commit()


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
            recommended = resp.json()  # [{book_id, hook_line, matched_trait, explanation}, ...]
            if not recommended:
                # 온보딩 미완료 등으로 ML 프로필이 아직 없는 유저 — 빈 추천 목록 반환
                return []
            isbn_list = [item["book_id"] for item in recommended]
        except httpx.HTTPError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ML 서버 연결 실패")
        except (ValueError, KeyError, TypeError):
            # ML이 200을 주면서 JSON이 깨졌거나 예상 필드가 빠진 경우(스키마 드리프트) —
            # 그대로 500을 흘려보내지 않고 "ML 서버 연결 실패"와 동일하게 503으로 응답.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ML 서버 응답 형식 오류")

    books_by_isbn = {b.isbn: b for b in book_service.get_books_by_isbn(db, isbn_list)}

    try:
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
    except (KeyError, TypeError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ML 서버 응답 형식 오류")


@router.get("/reviews/{review_id}/similar-books", response_model=list[SimilarReviewRecommendationOut])
async def get_similar_books_for_review(
    review_id: uuid.UUID,
    n: int = Query(default=3, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[SimilarReviewRecommendationOut]:
    """리뷰 상세의 '유사 리뷰 기반 책 추천' — ML 서버(/similar-books)를 호출해
    이 리뷰와 결이 비슷한 책을 찾는다. UI_DESIGN_SPEC.md §6.8 규칙대로 원 리뷰가
    속한 도서(isbn)는 결과에서 제외한다(ML 쪽에서 exclude_book_id로 처리).

    ML의 임베딩 계산은 요청마다 실시간으로 돌아 10초 안팎이 걸리므로(캐시 미스 시),
    review_id 기준으로 결과를 DB(similar_books_cache)에 캐싱해 재조회는 즉시 응답한다.
    캐시가 없을 때만 ML을 호출하며, 이때는 타임아웃을 넉넉히 잡는다(과거 10초 타임아웃이
    실제 계산 시간보다 짧아 매번 빈 목록으로 조용히 대체되던 버그가 있었다).

    이 섹션은 화면의 보조 섹션이라(프론트가 isError를 소비하지 않음) ML 장애
    시에도 원래 더미 구현과 같은 "절대 실패하지 않는" 계약을 유지한다 — 503 대신
    빈 목록(또는 있으면 오래된 캐시)을 반환해 기존 빈 상태 문구로 자연스럽게 대체되게 한다.
    """
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")

    cache_row = db.get(SimilarBooksCache, review_id)
    now = datetime.now(timezone.utc)
    if cache_row is not None and now - cache_row.computed_at < SIMILAR_BOOKS_CACHE_TTL:
        similar = cache_row.results
    else:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{settings.ml_server_url}/similar-books",
                    json={
                        "isbn": review.isbn,
                        "emotion_tags": review.emotion_tags,
                        "liked_points": review.liked_points,
                        "disliked_points": review.disliked_points,
                        "content": review.content,
                        "k": n,
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()
                similar = resp.json()  # [{book_id, snippet, reason}, ...]
                _save_similar_books_cache(db, review_id, similar)
            except httpx.HTTPError:
                similar = cache_row.results if cache_row is not None else []
            except (ValueError, KeyError, TypeError):
                similar = cache_row.results if cache_row is not None else []

    books_by_isbn = {
        b.isbn: b
        for b in book_service.get_books_by_isbn(db, [item["book_id"] for item in similar])
    }

    try:
        return [
            SimilarReviewRecommendationOut(
                sourceReviewId=str(review_id),
                bookId=item["book_id"],
                matchedReviewSnippet=item["snippet"],
                similarityReason=item["reason"],
            )
            for item in similar
            if item["book_id"] in books_by_isbn
        ]
    except (KeyError, TypeError):
        return []
