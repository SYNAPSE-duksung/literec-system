"""books_naver.jsonl / llm_reviews.jsonl을 DB에 upsert하는 시드 스크립트 (정본).

실행 전 `alembic upgrade head`로 스키마가 먼저 적용되어 있어야 한다.
실행: backend/ 디렉터리에서 `uv run python scripts/seed.py`
반복 실행해도 중복 적재되지 않도록 전부 upsert(ON CONFLICT DO UPDATE)로 처리한다.

LLM 생성 리뷰(440건)는 `결-bot` 유저에 귀속시키고, `created_at`을 llm_reviews.jsonl이
최초로 커밋된 시각(커밋 1c96df5, 2026-07-26 23:28:11 +09:00)으로 고정, `is_processed=True`로
적재한다 — server_default=now()에 맡기면 재시딩할 때마다 "시드 실행 시각"이 찍혀 440건이
전부 같은 순간에 작성된 것처럼 보이는 문제가 있었다.
"""

import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal  # noqa: E402
from app.models import Book, BookAspect, Review, User  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
BOOKS_FILE = DATA_DIR / "books_naver.jsonl"
REVIEWS_FILE = DATA_DIR / "llm_reviews.jsonl"
REAL_REVIEWS_FILE = DATA_DIR / "real_reviews.jsonl"

# llm_reviews.jsonl에는 자연 유니크 키가 없어, 재실행해도 같은 id가 나오도록
# 고정된 네임스페이스로 uuid5를 생성한다(리뷰 upsert 키로 사용).
SEED_REVIEW_NAMESPACE = uuid.UUID("03ae0456-9996-46c8-8190-59c8c579f3f4")

LLM_BOT_NAME = "결-bot"

KST = timezone(timedelta(hours=9))
LLM_REVIEWS_SEED_CREATED_AT = datetime(2026, 7, 26, 23, 28, 11, tzinfo=KST)
# real_reviews.jsonl 최초 커밋 시각(커밋 0215ef8, 2026-08-23 22:28:23 +09:00) — LLM_REVIEWS와
# 동일한 이유로 재시딩할 때마다 "시드 실행 시각"이 찍히는 걸 막기 위해 고정한다.
REAL_REVIEWS_SEED_CREATED_AT = datetime(2026, 8, 23, 22, 28, 23, tzinfo=KST)

SECTION_HEADER_RE = re.compile(r"^##\s*(\d+)\.", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
BOLD_PHRASE_RE = re.compile(r"\*\*(.+?)\*\*")


def _split_sections(perplexity_review: str) -> dict[int, str]:
    """'## N. ...' 헤더 기준으로 본문을 섹션 번호별로 분리한다."""
    parts = SECTION_HEADER_RE.split(perplexity_review)
    # parts = [머리말, "1", 본문1, "2", 본문2, ...]
    sections: dict[int, str] = {}
    for i in range(1, len(parts), 2):
        sections[int(parts[i])] = parts[i + 1]
    return sections


def _extract_bullets(section_body: str) -> list[str]:
    """최상위 '- ' 불릿만 추출한다(들여쓰기된 하위 근거 불릿은 제외).

    각 불릿의 **강조** 구절을 대표 키워드로 우선 사용하고, 없으면 마크다운 링크를
    제거한 본문을 사용한다.
    """
    items: list[str] = []
    for line in section_body.splitlines():
        if not line.startswith("- "):
            continue
        content = line[2:]
        bold_match = BOLD_PHRASE_RE.search(content)
        text = bold_match.group(1) if bold_match else MD_LINK_RE.sub("", content)
        text = text.strip(' :"')
        if text:
            items.append(text)
    return items


def parse_book_aspects(perplexity_review: str) -> dict[str, list[str]]:
    sections = _split_sections(perplexity_review)
    return {
        "liked_elements": _extract_bullets(sections.get(1, "")),
        "disliked_elements": _extract_bullets(sections.get(2, "")),
        "emotion_experience": _extract_bullets(sections.get(4, "")),
        # perplexity_review의 5개 섹션 중 직접 대응하는 항목이 없어 빈 배열로 시작
        # (report/LiteRec_Backend_ClaudeCode_Brief.md §6.1)
        "themes": [],
        "reading_context": [],
    }


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def get_or_create_llm_bot(db: Session) -> User:
    bot = db.query(User).filter(User.name == LLM_BOT_NAME, User.auth_provider == "local").first()
    if bot is not None:
        return bot
    bot = User(name=LLM_BOT_NAME, email=None, password_hash=None, auth_provider="local")
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


def seed_books(db: Session) -> int:
    records = _read_jsonl(BOOKS_FILE)
    for row in records:
        book_stmt = pg_insert(Book).values(
            isbn=row["isbn"],
            title=row["title"],
            author=row["author"],
            publisher=row["publisher"],
            cover_url=row.get("image"),
            synopsis=row.get("description"),
        )
        book_stmt = book_stmt.on_conflict_do_update(
            index_elements=[Book.isbn],
            set_={
                "title": book_stmt.excluded.title,
                "author": book_stmt.excluded.author,
                "publisher": book_stmt.excluded.publisher,
                "cover_url": book_stmt.excluded.cover_url,
                "synopsis": book_stmt.excluded.synopsis,
            },
        )
        db.execute(book_stmt)

        aspects = parse_book_aspects(row.get("perplexity_review", ""))
        aspect_stmt = pg_insert(BookAspect).values(isbn=row["isbn"], **aspects)
        aspect_stmt = aspect_stmt.on_conflict_do_update(
            index_elements=[BookAspect.isbn],
            set_={
                "emotion_experience": aspect_stmt.excluded.emotion_experience,
                "liked_elements": aspect_stmt.excluded.liked_elements,
                "disliked_elements": aspect_stmt.excluded.disliked_elements,
                "themes": aspect_stmt.excluded.themes,
                "reading_context": aspect_stmt.excluded.reading_context,
            },
        )
        db.execute(aspect_stmt)

    db.commit()
    return len(records)


def seed_reviews(db: Session) -> int:
    records = _read_jsonl(REVIEWS_FILE)
    bot = get_or_create_llm_bot(db)

    for row in records:
        review_id = uuid.uuid5(
            SEED_REVIEW_NAMESPACE, f"{row['isbn']}:{row['persona']}:{row['review_index']}"
        )
        stmt = pg_insert(Review).values(
            id=review_id,
            isbn=row["isbn"],
            user_id=bot.id,
            source="llm_generated",
            persona=row["persona"],
            content=row["content"],
            emotion_tags=[],
            liked_points=[],
            disliked_points=[],
            created_at=LLM_REVIEWS_SEED_CREATED_AT,
            is_processed=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Review.id],
            set_={
                "content": stmt.excluded.content,
                "persona": stmt.excluded.persona,
                "user_id": stmt.excluded.user_id,
                "created_at": stmt.excluded.created_at,
                "is_processed": stmt.excluded.is_processed,
            },
        )
        db.execute(stmt)

    db.commit()
    return len(records)


def seed_real_reviews(db: Session) -> int:
    """구글폼으로 수집한 실제 독자 리뷰(real_reviews.jsonl)를 reviews에 upsert한다.
    is_processed는 일부러 False로 두고 upsert 시에도 갱신하지 않는다 — 아직 5축으로
    구조화된 적이 없으니 structure-reviews CronJob이 나중에 실제로 처리하게 하기 위함
    (재시딩 때마다 False로 되돌아가 이미 처리된 리뷰까지 Upstage로 재구조화되는 것 방지)."""
    records = _read_jsonl(REAL_REVIEWS_FILE)

    for row in records:
        review_id = uuid.uuid5(SEED_REVIEW_NAMESPACE, f"real:{row['isbn']}:{row['review_index']}")
        stmt = pg_insert(Review).values(
            id=review_id,
            isbn=row["isbn"],
            user_id=None,
            source="user",
            content=row["content"],
            emotion_tags=[],
            liked_points=[],
            disliked_points=[],
            created_at=REAL_REVIEWS_SEED_CREATED_AT,
            is_processed=False,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Review.id],
            set_={
                "content": stmt.excluded.content,
                "created_at": stmt.excluded.created_at,
            },
        )
        db.execute(stmt)

    db.commit()
    return len(records)


def main() -> None:
    db = SessionLocal()
    try:
        book_count = seed_books(db)
        review_count = seed_reviews(db)
        real_review_count = seed_real_reviews(db)
    finally:
        db.close()
    print(f"books + book_aspects upserted: {book_count}")
    print(f"reviews upserted: {review_count}")
    print(f"real reviews upserted: {real_review_count}")


if __name__ == "__main__":
    main()
