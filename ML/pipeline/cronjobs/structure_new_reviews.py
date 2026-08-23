"""STEP8 — 신규 리뷰(게시판 실사용자 작성 등) 5축 자동 구조화 배치.

`reviews.is_processed = FALSE`인 리뷰를 책(isbn) 단위로 묶어 Upstage Solar API로
구조화하고, 결과를 `review_axes` 테이블에 저장한다. 프롬프트/API 호출/검증 로직은
`data/src/llm_review/{prompt_builder.py, structure_reviews.py}`의 기존 구현을 그대로
재사용한다(초기 440건을 구조화한 것과 동일한 로직 — 새로 만들지 않음).

책 하나를 구조화하는 데 성공하면 그 책에 속한 리뷰들만 `review_axes` upsert +
`is_processed = TRUE`로 표시한다(한 트랜잭션). 실패한 책의 리뷰는 FALSE로 남아
다음 실행 때 재시도된다 — 원안(daily는 임베딩만 하고 weekly가 is_processed를
일괄 갱신)과 달리, 구조화에 실패한 리뷰가 "처리됨"으로 영구 표시되는 정합성
버그를 피하기 위해 구조화 성공 여부에 정확히 맞춰 갱신한다.

실행(저장소 루트에서): `uv run --project ML python -m ML.pipeline.cronjobs.structure_new_reviews`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "data" / "src" / "llm_review"))
from structure_reviews import structure_book_with_retry  # noqa: E402

from ML.pipeline.aspect_based_model import DEFAULT_DATABASE_URL, _to_psycopg_dsn  # noqa: E402

DEFAULT_MODEL = "solar-pro3-260323"
PLACEHOLDER_SENTIMENT = "실제 사용자 리뷰"


def fetch_pending_reviews(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, isbn, content FROM reviews WHERE is_processed = false ORDER BY isbn"
        )
        rows = cur.fetchall()
    return [{"id": row[0], "isbn": row[1], "content": row[2]} for row in rows]


def group_by_isbn(reviews: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for review in reviews:
        groups.setdefault(review["isbn"], []).append(review)
    return groups


def save_book_result(conn, reviews: list[dict], structured: list[dict]) -> None:
    """reviews와 structured는 같은 순서(인덱스)로 대응한다. 한 책 전체를 한
    트랜잭션으로 upsert + is_processed 갱신한다."""
    structured_by_index = {item["review_index"]: item for item in structured}
    with conn.cursor() as cur:
        for i, review in enumerate(reviews):
            item = structured_by_index[i]
            cur.execute(
                """
                INSERT INTO review_axes
                    (review_id, emotion_experience, liked_elements, disliked_elements, themes, reading_context)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (review_id) DO UPDATE SET
                    emotion_experience = excluded.emotion_experience,
                    liked_elements = excluded.liked_elements,
                    disliked_elements = excluded.disliked_elements,
                    themes = excluded.themes,
                    reading_context = excluded.reading_context,
                    structured_at = now()
                """,
                (
                    review["id"],
                    item.get("정서_경험"),
                    item.get("좋았던_요소"),
                    item.get("별로였던_요소"),
                    item.get("소재_및_주제"),
                    item.get("독서_경험_맥락"),
                ),
            )
            cur.execute("UPDATE reviews SET is_processed = true WHERE id = %s", (review["id"],))
    conn.commit()


def run() -> None:
    import psycopg

    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print("[structure_new_reviews] UPSTAGE_API_KEY가 없습니다.", file=sys.stderr)
        sys.exit(1)
    model = os.environ.get("UPSTAGE_MODEL", DEFAULT_MODEL)
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    with psycopg.connect(_to_psycopg_dsn(database_url)) as conn:
        pending = fetch_pending_reviews(conn)
        if not pending:
            print("[structure_new_reviews] 신규 리뷰 없음, 종료")
            return

        groups = group_by_isbn(pending)
        done, failed = 0, []
        for isbn, reviews in groups.items():
            print(f"[structure_new_reviews] {isbn} - 리뷰 {len(reviews)}건 구조화 중...")
            prompt_reviews = [
                {"review_index": i, "sentiment": PLACEHOLDER_SENTIMENT, "content": r["content"]}
                for i, r in enumerate(reviews)
            ]
            try:
                structured = structure_book_with_retry(prompt_reviews, api_key, model)
                save_book_result(conn, reviews, structured)
            except Exception as e:  # noqa: BLE001 — 한 책 실패가 나머지 책 처리를 막지 않음
                print(f"  [실패] {isbn}: {e}", file=sys.stderr)
                conn.rollback()
                failed.append(isbn)
                continue
            done += 1

        print(f"[structure_new_reviews] 완료: {done}권 구조화, {len(failed)}권 실패")
        if failed:
            print(f"[structure_new_reviews] 실패 ISBN 목록: {failed}")


if __name__ == "__main__":
    run()
