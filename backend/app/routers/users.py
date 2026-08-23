import uuid

import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import (
    BookReaction,
    RecommendationEvent,
    RefreshToken,
    Review,
    ReviewReaction,
    User,
    UserProfile,
)
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
                timeout=30.0,
            )
    except httpx.HTTPError as exc:
        print(f"[users] ML /profile/build 호출 실패(user_id={current_user.id}): {exc}")

    return _profile_out(current_user.id, profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """회원 탈퇴. 리뷰 자체는 다른 유저에게도 유용한 컨텐츠이자 추천 모델의 학습
    데이터라 삭제하지 않고 작성자만 지운다 — reviews.user_id는 이미 nullable이고
    llm_generated 리뷰(결-bot)도 이미 이 방식으로 작성자 없이 존재한다."""
    # synchronize_session=False 필수 — 이 세션에 이미 로드된 Review 객체가 있으면(예:
    # 방금 리뷰를 쓴 직후 탈퇴하는 경우) review.author 관계 속성이 여전히 current_user를
    # 가리키고 있어서, 기본 동기화 전략(evaluate)이 컬럼만 None으로 바꿔놔도 뒤이은
    # commit()의 flush에서 관계가 FK 컬럼을 다시 덮어써 버린다(그러면 아래 유저 삭제가
    # FK 위반으로 실패한다). synchronize_session=False로 세션 동기화 자체를 건너뛴다.
    db.query(Review).filter(Review.user_id == current_user.id).update(
        {"user_id": None}, synchronize_session=False
    )
    db.query(ReviewReaction).filter(ReviewReaction.user_id == current_user.id).delete()
    db.query(BookReaction).filter(BookReaction.user_id == current_user.id).delete()
    db.query(RecommendationEvent).filter(RecommendationEvent.user_id == current_user.id).delete()
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).delete()
    db.query(UserProfile).filter(UserProfile.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()


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
