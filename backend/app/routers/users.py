import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BookReaction, ReviewReaction, User, UserProfile
from app.schemas.book import BookReactionsOut
from app.schemas.user import UserProfileOut, UserProfileUpdate
from app.security import get_current_user

router = APIRouter(prefix="/api/users/me", tags=["users"])


def _profile_out(user_id: uuid.UUID, profile: UserProfile | None) -> UserProfileOut:
    return UserProfileOut(
        userId=str(user_id),
        preferredEmotions=profile.preferred_emotions if profile else [],
        avoidedTraits=profile.avoided_traits if profile else [],
    )


@router.get("/profile", response_model=UserProfileOut)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileOut:
    profile = db.get(UserProfile, current_user.id)
    return _profile_out(current_user.id, profile)


@router.patch("/profile", response_model=UserProfileOut)
def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileOut:
    profile = db.get(UserProfile, current_user.id)
    if profile is None:
        profile = UserProfile(
            user_id=current_user.id,
            preferred_emotions=payload.preferredEmotions or [],
            avoided_traits=payload.avoidedTraits or [],
        )
        db.add(profile)
    else:
        if payload.preferredEmotions is not None:
            profile.preferred_emotions = payload.preferredEmotions
        if payload.avoidedTraits is not None:
            profile.avoided_traits = payload.avoidedTraits

    db.commit()
    db.refresh(profile)
    return _profile_out(current_user.id, profile)


@router.get("/review-reactions")
def get_review_reactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    rows = db.query(ReviewReaction).filter(ReviewReaction.user_id == current_user.id).all()
    return {str(row.review_id): row.reaction for row in rows}


@router.get("/book-reactions", response_model=BookReactionsOut)
def get_book_reactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookReactionsOut:
    rows = db.query(BookReaction).filter(BookReaction.user_id == current_user.id).all()
    return BookReactionsOut(
        likedBookIds=[row.isbn for row in rows if row.reaction == "like"],
        dislikedBookIds=[row.isbn for row in rows if row.reaction == "dislike"],
    )
