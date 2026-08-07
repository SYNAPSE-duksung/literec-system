"""
이미 저장된 리뷰 JSONL 파일에서 MIN_CONTENT_LENGTH(700자) 미만인 리뷰만 골라
해당 항목만 재생성해 같은 파일에 덮어쓴다. persona/sentiment는 고정한 채
content만 다시 쓰므로 다른 리뷰나 책 구성에는 영향이 없다.

사용법(data 폴더에 들어와서):
  uv run python src/llm_review/fix_short_reviews.py processed/llm_reviews_ver2.jsonl
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from generate_llm_reviews import (
    DEFAULT_MODEL,
    ENV_PATH,
    JSONL_PATH,
    MIN_CONTENT_LENGTH,
    load_books,
    regenerate_flagged_reviews,
)
from prompt_builder import load_few_shot_example, load_personas


def main():
    if len(sys.argv) != 2:
        print("사용법: python fix_short_reviews.py <jsonl 파일 경로 (data/ 기준)>")
        sys.exit(1)

    target_path = Path(__file__).parent.parent.parent / sys.argv[1]
    if not target_path.exists():
        print(f"파일을 찾을 수 없습니다: {target_path}", file=sys.stderr)
        sys.exit(1)

    load_dotenv(ENV_PATH)
    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print("data/.env에 UPSTAGE_API_KEY가 없습니다.", file=sys.stderr)
        sys.exit(1)
    model = os.environ.get("UPSTAGE_MODEL", DEFAULT_MODEL)

    with open(target_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    short_records = [r for r in records if len(r["content"]) < MIN_CONTENT_LENGTH]
    print(f"[대상] {MIN_CONTENT_LENGTH}자 미만 {len(short_records)}건", file=sys.stderr)

    books_by_isbn = {b["isbn"]: b for b in load_books(JSONL_PATH)}
    personas = load_personas()
    few_shot_example = load_few_shot_example()

    by_isbn: dict[str, list[dict]] = {}
    for r in short_records:
        by_isbn.setdefault(r["isbn"], []).append(r)

    for isbn, reviews in by_isbn.items():
        book = books_by_isbn[isbn]
        print(f"[{isbn}] {book['title']} - {len(reviews)}건 재생성", file=sys.stderr)
        regenerate_flagged_reviews(book, reviews, api_key, model, personas, few_shot_example)

    with open(target_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    still_short = sum(1 for r in records if len(r["content"]) < MIN_CONTENT_LENGTH)
    print(f"[완료] {target_path} 갱신. 여전히 미달: {still_short}건", file=sys.stderr)


if __name__ == "__main__":
    main()
