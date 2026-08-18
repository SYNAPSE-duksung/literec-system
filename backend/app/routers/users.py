import uuid

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
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
async def update_profile(
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

    # ML 서버에 병합된 전체 프로필을 등록(온보딩·마이페이지 재설정 공용 — 부분 PATCH여도
    # 항상 DB에 최종 저장된 전체 값을 보낸다, 안 그러면 안 보낸 필드가 빈 배열로 ML에
    # 전달되어 기존 선호 신호가 사라진다). 실패해도 프로필 저장 자체는 성공 처리한다.
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.ml_server_url}/profile/build",
                json={
                    "user_id": str(current_user.id),
                    "preferred_emotions": profile.preferred_emotions,
                    "avoided_traits": profile.avoided_traits,
                },
                timeout=10.0,
            )
    except httpx.HTTPError:
        pass

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
