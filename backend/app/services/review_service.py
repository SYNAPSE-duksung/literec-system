import uuid

from sqlalchemy.orm import Session

from app.models import Review, ReviewReaction
from app.schemas.review import ReviewOut

# 실사용자 리뷰가 아닌 LLM 생성 리뷰(user_id=None)의 프론트 표기용 placeholder.
# 실제 로그인 유저 uuid와 절대 겹치지 않으므로 "내가 쓴 글" 필터(userId 비교)에 안전하다.
LLM_REVIEW_USER_ID = "llm"


def to_review_out(review: Review) -> ReviewOut:
    author_name = review.author.name if review.author else (review.persona or "")
    return ReviewOut(
        id=str(review.id),
        bookId=review.isbn,
        userId=str(review.user_id) if review.user_id else LLM_REVIEW_USER_ID,
        userName=author_name,
        content=review.content,
        liked=review.liked_points,
        disliked=review.disliked_points,
        emotion=review.emotion_tags,
        likeCount=review.like_count,
        createdAt=review.created_at.isoformat(),
    )


def _adjust_count(review: Review, reaction: str, delta: int) -> None:
    if reaction == "like":
        review.like_count = max(0, review.like_count + delta)
    else:
        review.dislike_count = max(0, review.dislike_count + delta)


def set_reaction(db: Session, review: Review, user_id: uuid.UUID, reaction: str) -> None:
    existing = db.get(ReviewReaction, {"review_id": review.id, "user_id": user_id})
    if existing is None:
        db.add(ReviewReaction(review_id=review.id, user_id=user_id, reaction=reaction))
        _adjust_count(review, reaction, +1)
    elif existing.reaction != reaction:
        _adjust_count(review, existing.reaction, -1)
        _adjust_count(review, reaction, +1)
        existing.reaction = reaction
    db.commit()


def clear_reaction(db: Session, review: Review, user_id: uuid.UUID) -> None:
    existing = db.get(ReviewReaction, {"review_id": review.id, "user_id": user_id})
    if existing is not None:
        _adjust_count(review, existing.reaction, -1)
        db.delete(existing)
        db.commit()
