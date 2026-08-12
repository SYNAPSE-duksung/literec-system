"""data/processed/books_naver.jsonl, llm_reviews.jsonl을 읽어 DB에 적재한다.

실행: backend/ 에서 `uv run python scripts/seed_data.py`
- books는 isbn 기준 upsert (재실행해도 안전).
- reviews는 source='llm_generated' 항목을 통째로 지우고 다시 채운다 (재실행 시 중복 방지).
"""

import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import Book, Review, User

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
BOOKS_FILE = DATA_DIR / "books_naver.jsonl"
REVIEWS_FILE = DATA_DIR / "llm_reviews.jsonl"

LLM_BOT_NAME = "결-bot"


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
    db.query(Review).filter(Review.source == "llm_generated").delete()
    for row in rows:
        db.add(
            Review(
                isbn=row["isbn"],
                user_id=bot.id,
                source="llm_generated",
                persona=row.get("persona"),
                content=row["content"],
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
