from fastapi import APIRouter, Depends, status
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
    db.commit()
    return {"status": "ok"}
