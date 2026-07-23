"""
data/processed/books_naver.jsonl의 도서 정보(+perplexity_review)를 바탕으로
Upstage Solar API를 호출해 책마다 페르소나 리뷰 5개(호 2 / 불호 2 / 혼재 1)를
생성하고 data/processed/llm_reviews.jsonl에 한 줄씩 append한다.

사용법:
  uv run python data/src/llm_review/generate_llm_reviews.py 0 0        # 인덱스 0번 책만
  uv run python data/src/llm_review/generate_llm_reviews.py 0 87       # 전체
  uv run python data/src/llm_review/generate_llm_reviews.py 0 87 --force  # 이미 처리된 isbn도 재생성

이미 OUTPUT_PATH에 존재하는 isbn은 기본적으로 건너뛴다(재실행 시 중복 API 호출 방지).
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from prompt_builder import build_prompt, load_few_shot_example, load_personas

JSONL_PATH = Path(__file__).parent.parent.parent / "processed" / "books_naver.jsonl"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "processed" / "llm_reviews.jsonl"
ENV_PATH = Path(__file__).parent.parent.parent / ".env"

UPSTAGE_API_URL = "https://api.upstage.ai/v1/chat/completions"
DEFAULT_MODEL = "solar-pro3-260323"

REQUEST_INTERVAL_SEC = 1.0
MAX_RETRIES = 3
MAX_VALIDATION_RETRIES = 3
REQUEST_TIMEOUT_SEC = 120

EXPECTED_SENTIMENT_COUNTS = {"호": 2, "불호": 2, "혼재": 1}
MIN_CONTENT_LENGTH = 800

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def load_books(jsonl_path: Path) -> list[dict]:
    with open(jsonl_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def call_upstage(prompt: str, api_key: str, model: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "max_tokens": 8000,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        UPSTAGE_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
                payload = json.load(response)
            return payload["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                print(f"  [재시도 {attempt}] HTTP {e.code}: {detail[:200]}", file=sys.stderr)
                time.sleep(2.0 * attempt)
                continue
            raise RuntimeError(f"Upstage API 호출 실패: HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES:
                print(f"  [재시도 {attempt}] {e}", file=sys.stderr)
                time.sleep(2.0 * attempt)
                continue
            raise RuntimeError(f"Upstage API 호출 실패: {e}") from e

    raise RuntimeError("Upstage API 호출 실패: 재시도 횟수 초과")


def parse_reviews(raw_content: str) -> list[dict]:
    cleaned = CODE_FENCE_RE.sub("", raw_content).strip()
    data = json.loads(cleaned)
    return data["reviews"]


def validate_reviews(reviews: list[dict], valid_personas: set[str]) -> list[str]:
    issues = []

    if len(reviews) != 5:
        issues.append(f"리뷰 개수가 5개가 아님: {len(reviews)}개")

    sentiment_counts: dict[str, int] = {}
    personas_seen: set[str] = set()
    for review in reviews:
        sentiment_counts[review["sentiment"]] = sentiment_counts.get(review["sentiment"], 0) + 1
        if review["persona"] not in valid_personas:
            issues.append(f"정의되지 않은 페르소나: {review['persona']}")
        if review["persona"] in personas_seen:
            issues.append(f"페르소나 중복: {review['persona']}")
        personas_seen.add(review["persona"])
        if len(review["content"]) < MIN_CONTENT_LENGTH:
            issues.append(f"{review['persona']} 리뷰 길이 부족: {len(review['content'])}자")

    if sentiment_counts != EXPECTED_SENTIMENT_COUNTS:
        issues.append(f"호/불호/혼재 구성이 기대와 다름: {sentiment_counts}")

    return issues


def generate_reviews_with_retry(
    prompt: str, api_key: str, model: str, valid_personas: set[str]
) -> list[dict]:
    reviews: list[dict] = []
    issues: list[str] = []
    current_prompt = prompt
    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        raw_content = call_upstage(current_prompt, api_key, model)
        reviews = parse_reviews(raw_content)
        issues = validate_reviews(reviews, valid_personas)
        if not issues:
            return reviews
        print(f"  [검증 재시도 {attempt}] {issues}", file=sys.stderr)
        issue_text = "\n".join(f"- {issue}" for issue in issues)
        current_prompt = (
            f"{prompt}\n\n"
            f"[이전 시도의 문제점 - 이번엔 반드시 고쳐서 다시 작성할 것]\n{issue_text}"
        )

    print(f"  [경고] 검증을 통과하지 못해 best-effort로 저장함: {issues}", file=sys.stderr)
    return reviews


def build_output_records(book: dict, reviews: list[dict]) -> list[dict]:
    return [
        {
            "isbn": book["isbn"],
            "book_title": book["title"],
            "review_index": i + 1,
            "persona": review["persona"],
            "persona_reason": review["persona_reason"],
            "sentiment": review["sentiment"],
            "content": review["content"],
        }
        for i, review in enumerate(reviews)
    ]


def load_processed_isbns(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    with open(output_path, encoding="utf-8") as f:
        return {json.loads(line)["isbn"] for line in f if line.strip()}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv[1:]

    if len(args) != 2:
        print("사용법: python generate_llm_reviews.py <시작인덱스> <끝인덱스> [--force]")
        print("예시:   python generate_llm_reviews.py 0 87")
        sys.exit(1)

    start, end = int(args[0]), int(args[1])

    load_dotenv(ENV_PATH)
    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print("data/.env에 UPSTAGE_API_KEY가 없습니다.", file=sys.stderr)
        sys.exit(1)
    model = os.environ.get("UPSTAGE_MODEL", DEFAULT_MODEL)

    books = load_books(JSONL_PATH)
    if not (0 <= start <= end < len(books)):
        raise ValueError(f"인덱스 범위가 올바르지 않습니다. (0 ~ {len(books) - 1} 사이여야 함)")

    personas = load_personas()
    few_shot_example = load_few_shot_example()
    valid_persona_names = {p["name"] for p in personas}
    processed_isbns = set() if force else load_processed_isbns(OUTPUT_PATH)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    done, skipped, failed = 0, 0, []
    for i in range(start, end + 1):
        book = books[i]
        isbn = book["isbn"]

        if isbn in processed_isbns:
            print(f"[{i}] {book['title']} (ISBN {isbn}) - 이미 처리됨, 건너뜀", file=sys.stderr)
            skipped += 1
            continue

        print(f"[{i}] {book['title']} (ISBN {isbn}) - 생성 중...", file=sys.stderr)
        try:
            prompt = build_prompt(book, personas, few_shot_example)
            reviews = generate_reviews_with_retry(prompt, api_key, model, valid_persona_names)
            records = build_output_records(book, reviews)
        except Exception as e:
            print(f"  [실패] {e}", file=sys.stderr)
            failed.append(isbn)
            time.sleep(REQUEST_INTERVAL_SEC)
            continue

        with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        done += 1
        time.sleep(REQUEST_INTERVAL_SEC)

    print(
        f"\n[완료] {done}권 생성, {skipped}권 건너뜀, {len(failed)}권 실패 -> {OUTPUT_PATH}",
        file=sys.stderr,
    )
    if failed:
        print(f"[실패 ISBN 목록] {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
