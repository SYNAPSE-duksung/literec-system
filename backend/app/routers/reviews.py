import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Book, Review, ReviewReaction, User
from app.schemas.review import ReviewCreate, ReviewOut, ReviewReactionRequest, ReviewUpdate
from app.security import get_current_user
from app.services import review_service

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewOut])
def list_reviews(
    filter: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ReviewOut]:
    reviews = (
        db.query(Review).options(joinedload(Review.author)).order_by(Review.created_at.desc()).all()
    )
    if filter and filter.strip():
        needle = filter.strip().lower()
        reviews = [
            r
            for r in reviews
            if needle in r.content.lower() or any(needle in tag.lower() for tag in r.emotion_tags)
        ]
    return [review_service.to_review_out(r) for r in reviews]


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: uuid.UUID, db: Session = Depends(get_db)) -> ReviewOut:
    review = db.query(Review).options(joinedload(Review.author)).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")
    return review_service.to_review_out(review)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReviewOut)
def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    book = db.get(Book, payload.isbn)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "도서를 찾을 수 없습니다.")

    review = Review(
        isbn=payload.isbn,
        user_id=current_user.id,
        source="user",
        content=payload.content,
        emotion_tags=payload.emotion,
        liked_points=payload.liked,
        disliked_points=payload.disliked,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    review.author = current_user
    return review_service.to_review_out(review)


@router.patch("/{review_id}", response_model=ReviewOut)
def update_review(
    review_id: uuid.UUID,
    payload: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewOut:
    review = db.query(Review).options(joinedload(Review.author)).filter(Review.id == review_id).first()
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")
    if review.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "본인이 작성한 기록만 수정할 수 있습니다.")

    review.content = payload.content
    review.emotion_tags = payload.emotion
    review.liked_points = payload.liked
    review.disliked_points = payload.disliked
    db.commit()
    db.refresh(review)
    return review_service.to_review_out(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")
    if review.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "본인이 작성한 기록만 삭제할 수 있습니다.")

    # review_reactions가 review_id를 참조하므로(FK), 리뷰 자체를 지우기 전에 먼저 지운다.
    db.query(ReviewReaction).filter(ReviewReaction.review_id == review.id).delete()
    db.delete(review)
    db.commit()


@router.post("/{review_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def set_review_reaction(
    review_id: uuid.UUID,
    payload: ReviewReactionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")
    review_service.set_reaction(db, review, current_user.id, payload.reaction)


@router.delete("/{review_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def clear_review_reaction(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "리뷰를 찾을 수 없습니다.")
    review_service.clear_reaction(db, review, current_user.id)
