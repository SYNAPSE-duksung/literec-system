from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RecommendationEvent, User
from app.schemas.event import RecommendationEventCreate
from app.security import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", status_code=status.HTTP_201_CREATED)
def log_event(
    payload: RecommendationEventCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    db.add(
        RecommendationEvent(
            user_id=current_user.id,
            book_id=payload.book_id,
            event_type=payload.event_type,
            source=payload.source,
            rank=payload.rank,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # book_id(isbn)가 books 테이블에 없는 경우 등 FK 위반 — 5xx 대신 명확한 4xx로 응답.
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "존재하지 않는 책입니다.")
    return {"status": "ok"}
