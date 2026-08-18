"""data/processed/books_naver.jsonl, llm_reviews.jsonl을 읽어 DB에 적재한다.

실행: backend/ 에서 `uv run python scripts/seed_data.py`
- books는 isbn 기준 upsert (재실행해도 안전).
- reviews는 source='llm_generated' 항목을 통째로 지우고 다시 채운다 (재실행 시 중복 방지).
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# `python scripts/seed_data.py`로 실행하면 sys.path[0]이 scripts/ 디렉터리가 되어
# app 패키지(backend/app/)를 못 찾는다 — backend/ 를 명시적으로 추가해준다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import Book, Review, ReviewReaction, User

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
BOOKS_FILE = DATA_DIR / "books_naver.jsonl"
REVIEWS_FILE = DATA_DIR / "llm_reviews.jsonl"

LLM_BOT_NAME = "결-bot"

# llm_reviews.jsonl 자체엔 작성 시각이 없어, 이 파일이 최초로 커밋된 시각(커밋 1c96df5,
# 2026-07-26 23:28:11 +09:00)을 대신 쓴다. server_default=now()에 맡기면 재시딩할 때마다
# "시드 실행 시각"으로 찍혀 440건이 전부 같은 순간에 작성된 것처럼 보이는 문제가 있었다.
KST = timezone(timedelta(hours=9))
LLM_REVIEWS_SEED_CREATED_AT = datetime(2026, 7, 26, 23, 28, 11, tzinfo=KST)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def seed_books(db) -> int:
    rows = load_jsonl(BOOKS_FILE)
    for row in rows:
        values = {
            "isbn": row["isbn"],
            "title": row["title"],
            "author": row["author"],
            "publisher": row["publisher"],
            "cover_url": row.get("image"),
            "synopsis": row.get("description"),
        }
        stmt = pg_insert(Book).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["isbn"],
            set_={k: v for k, v in values.items() if k != "isbn"},
        )
        db.execute(stmt)
    db.commit()
    return len(rows)


def get_or_create_llm_bot(db) -> User:
    bot = db.query(User).filter(User.name == LLM_BOT_NAME, User.auth_provider == "local").first()
    if bot is not None:
        return bot
    bot = User(name=LLM_BOT_NAME, email=None, password_hash=None, auth_provider="local")
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


def seed_reviews(db) -> int:
    rows = load_jsonl(REVIEWS_FILE)
    bot = get_or_create_llm_bot(db)

    # LLM 리뷰를 통째로 지웠다가 다시 넣기 전에, 그 리뷰들을 참조하는 반응(좋아요/싫어요)부터
    # 지워야 한다 — 안 그러면 review_reactions FK 제약 위반으로 재시딩이 실패한다
    # (실사용자가 게시판에서 LLM 리뷰에 반응 하나만 남겨도 다음 재시딩이 깨짐).
    llm_review_ids = [
        r.id for r in db.query(Review).filter(Review.source == "llm_generated").all()
    ]
    if llm_review_ids:
        db.query(ReviewReaction).filter(ReviewReaction.review_id.in_(llm_review_ids)).delete(
            synchronize_session=False
        )
    db.query(Review).filter(Review.source == "llm_generated").delete()
    for row in rows:
        db.add(
            Review(
                isbn=row["isbn"],
                user_id=bot.id,
                source="llm_generated",
                persona=row.get("persona"),
                content=row["content"],
                created_at=LLM_REVIEWS_SEED_CREATED_AT,
                is_processed=True,
            )
        )
    db.commit()
    return len(rows)


def main() -> None:
    db = SessionLocal()
    try:
        n_books = seed_books(db)
        n_reviews = seed_reviews(db)
    finally:
        db.close()
    print(f"적재 완료 — books: {n_books}, reviews: {n_reviews}")


if __name__ == "__main__":
    main()
