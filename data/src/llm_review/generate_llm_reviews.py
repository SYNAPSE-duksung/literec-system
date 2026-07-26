"""
data/processed/books_naver.jsonl의 도서 정보(+perplexity_review)를 바탕으로
Upstage Solar API를 호출해 책마다 페르소나 리뷰 5개(호 2 / 불호 2 / 혼재 1)를
생성하고 data/processed/llm_reviews.jsonl에 한 줄씩 append한다.

사용법(data 폴더에 들어와서):
  uv run python src/llm_review/generate_llm_reviews.py 0 0        # 인덱스 0번 책만
  uv run python src/llm_review/generate_llm_reviews.py 0 87       # 전체
  uv run python src/llm_review/generate_llm_reviews.py 0 87 --force  # 이미 처리된 isbn도 재생성

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

from prompt_builder import (
    build_prompt,
    build_single_review_prompt,
    load_few_shot_example,
    load_personas,
)

JSONL_PATH = Path(__file__).parent.parent.parent / "processed" / "books_naver.jsonl"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "processed" / "llm_reviews.jsonl"
ENV_PATH = Path(__file__).parent.parent.parent / ".env"

UPSTAGE_API_URL = "https://api.upstage.ai/v1/chat/completions"
DEFAULT_MODEL = "solar-pro3-260323"

REQUEST_INTERVAL_SEC = 1.0
MAX_RETRIES = 3
MAX_VALIDATION_RETRIES = 3  # 페르소나/구성(치명적 오류) 재시도 횟수
MAX_LENGTH_RETRIES = 3  # 분량 미달 리뷰 1개당 재생성 재시도 횟수
REQUEST_TIMEOUT_SEC = 120

EXPECTED_SENTIMENT_COUNTS = {"호": 2, "불호": 2, "혼재": 1}
MIN_CONTENT_LENGTH = 700
MAX_CONTENT_LENGTH = 1500

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


def parse_single_review_content(raw_content: str) -> str:
    cleaned = CODE_FENCE_RE.sub("", raw_content).strip()
    data = json.loads(cleaned)
    return data["content"]


def validate_structure(reviews: list[dict], valid_personas: set[str]) -> list[str]:
    """치명적 오류만 검증한다: 리뷰 개수, 정의되지 않은 페르소나, 페르소나 중복,
    호/불호/혼재 구성. 분량은 여기서 다루지 않고 별도 단계에서 부분 재생성한다.

    정의되지 않은 페르소나가 하나라도 있으면 무슨 일이 있어도 통과시키지 않는다
    (호출부에서 재시도 소진 시 best-effort 저장 없이 예외를 던진다).
    """
    issues = []

    if len(reviews) != 5:
        issues.append(f"리뷰 개수가 5개가 아님: {len(reviews)}개")
        return issues

    sentiment_counts: dict[str, int] = {}
    personas_seen: set[str] = set()
    for review in reviews:
        persona = review.get("persona")
        sentiment_counts[review.get("sentiment")] = (
            sentiment_counts.get(review.get("sentiment"), 0) + 1
        )
        if persona not in valid_personas:
            issues.append(f"정의되지 않은 페르소나: {persona}")
        if persona in personas_seen:
            issues.append(f"페르소나 중복: {persona}")
        personas_seen.add(persona)

    if sentiment_counts != EXPECTED_SENTIMENT_COUNTS:
        issues.append(f"호/불호/혼재 구성이 기대와 다름: {sentiment_counts}")

    return issues


def find_short_review_indices(reviews: list[dict]) -> list[int]:
    return [i for i, review in enumerate(reviews) if len(review["content"]) < MIN_CONTENT_LENGTH]


def distance_to_length_range(text: str) -> int:
    """MIN_CONTENT_LENGTH~MAX_CONTENT_LENGTH 범위까지의 거리(범위 안이면 0)."""
    n = len(text)
    if n < MIN_CONTENT_LENGTH:
        return MIN_CONTENT_LENGTH - n
    if n > MAX_CONTENT_LENGTH:
        return n - MAX_CONTENT_LENGTH
    return 0


def regenerate_short_reviews(
    book: dict,
    reviews: list[dict],
    api_key: str,
    model: str,
    personas: list[dict],
    few_shot_example: dict,
) -> list[dict]:
    """분량 미달 리뷰만 골라 같은 페르소나/sentiment로 본문만 다시 쓴다.

    persona/sentiment는 그대로 고정한 채 content만 재생성하므로, 이 과정에서
    페르소나가 재배정되는 일이 없어 다른 리뷰와의 페르소나 중복이 발생할 수 없다.
    MIN_CONTENT_LENGTH~MAX_CONTENT_LENGTH 범위에 드는 결과가 나오면 즉시 채택하고,
    끝까지 범위에 못 들면 그중 가장 범위에 가까운(짧으면 가장 긴, 넘치면 가장 짧은) 버전을 쓴다.
    """
    persona_by_name = {p["name"]: p for p in personas}

    for idx in find_short_review_indices(reviews):
        review = reviews[idx]
        persona = persona_by_name[review["persona"]]
        best_content = review["content"]
        in_range_content = None

        for attempt in range(1, MAX_LENGTH_RETRIES + 1):
            single_prompt = build_single_review_prompt(
                book,
                persona,
                review["sentiment"],
                best_content,
                few_shot_example,
                MIN_CONTENT_LENGTH,
                MAX_CONTENT_LENGTH,
            )
            try:
                raw = call_upstage(single_prompt, api_key, model)
                new_content = parse_single_review_content(raw)
            except Exception as e:
                print(f"  [{review['persona']} 분량 재생성 {attempt} 실패] {e}", file=sys.stderr)
                continue

            length = len(new_content)
            print(
                f"  [{review['persona']} 분량 재생성 {attempt}] {length}자 "
                f"(목표 {MIN_CONTENT_LENGTH}~{MAX_CONTENT_LENGTH}자)",
                file=sys.stderr,
            )

            if MIN_CONTENT_LENGTH <= length <= MAX_CONTENT_LENGTH:
                in_range_content = new_content
                break

            # 범위 밖이면, 기존 best보다 "범위에 더 가까운" 경우에만 교체한다.
            if distance_to_length_range(new_content) < distance_to_length_range(best_content):
                best_content = new_content

        if in_range_content is not None:
            review["content"] = in_range_content
            continue

        if len(best_content) < MIN_CONTENT_LENGTH:
            print(
                f"  [경고] {review['persona']} 리뷰가 끝내 {MIN_CONTENT_LENGTH}자를 넘지 못해 "
                f"최선 버전({len(best_content)}자)만 남김",
                file=sys.stderr,
            )
        elif len(best_content) > MAX_CONTENT_LENGTH:
            print(
                f"  [경고] {review['persona']} 리뷰가 {MAX_CONTENT_LENGTH}자를 초과한 채로 "
                f"저장됨({len(best_content)}자)",
                file=sys.stderr,
            )
        review["content"] = best_content

    return reviews


def generate_reviews_with_retry(
    book: dict,
    prompt: str,
    api_key: str,
    model: str,
    valid_personas: set[str],
    personas: list[dict],
    few_shot_example: dict,
) -> list[dict]:
    reviews: list[dict] = []
    issues: list[str] = []
    current_prompt = prompt

    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        raw_content = call_upstage(current_prompt, api_key, model)
        reviews = parse_reviews(raw_content)
        issues = validate_structure(reviews, valid_personas)
        if not issues:
            break
        print(f"  [구성 검증 재시도 {attempt}] {issues}", file=sys.stderr)
        issue_text = "\n".join(f"- {issue}" for issue in issues)
        current_prompt = (
            f"{prompt}\n\n"
            f"[이전 시도의 문제점 - 이번엔 반드시 고쳐서 다시 작성할 것]\n{issue_text}"
        )
    else:
        raise RuntimeError(
            f"페르소나/구성 검증을 통과하지 못해 생성을 포기함(저장하지 않음): {issues}"
        )

    return regenerate_short_reviews(book, reviews, api_key, model, personas, few_shot_example)


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
            reviews = generate_reviews_with_retry(
                book, prompt, api_key, model, valid_persona_names, personas, few_shot_example
            )
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
