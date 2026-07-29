"""
data/processed/books_naver.jsonl의 도서 정보(+perplexity_review)를 바탕으로
Upstage Solar API를 호출해 책마다 페르소나 리뷰 5개(호 2 / 불호 2 / 혼재 1)를
생성하고 data/processed/llm_reviews.jsonl에 한 줄씩 append한다.

사용법(data 폴더에 들어와서):
  uv run python src/llm_review/generate_llm_reviews.py 0 0        # 인덱스 0번 책만
  uv run python src/llm_review/generate_llm_reviews.py 0 87       # 전체
  uv run python src/llm_review/generate_llm_reviews.py 0 87 --force  # 이미 처리된 isbn도 재생성
  uv run python src/llm_review/generate_llm_reviews.py 0 87 --output llm_reviews_ver2.jsonl
      # data/processed/ 아래 다른 파일명으로 저장(기본값: llm_reviews.jsonl)

이미 출력 파일에 존재하는 isbn은 기본적으로 건너뛴다(재실행 시 중복 API 호출 방지).
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
    has_forbidden_brackets,
    load_few_shot_example,
    load_personas,
)

PROCESSED_DIR = Path(__file__).parent.parent.parent / "processed"
JSONL_PATH = PROCESSED_DIR / "books_naver.jsonl"
DEFAULT_OUTPUT_PATH = PROCESSED_DIR / "llm_reviews.jsonl"
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


def review_issue_score(text: str) -> int:
    """길이 범위 이탈 + 금지 문장부호 포함 여부를 하나의 점수로 합친다. 0이면 완전히 통과.

    금지 문장부호(겹낫표/홑낫표) 포함은 길이 문제보다 훨씬 심각하게 취급해, 길이가
    약간 안 맞더라도 문장부호가 없는 버전을 항상 우선하도록 큰 페널티를 더한다.
    """
    n = len(text)
    if n < MIN_CONTENT_LENGTH:
        score = MIN_CONTENT_LENGTH - n
    elif n > MAX_CONTENT_LENGTH:
        score = n - MAX_CONTENT_LENGTH
    else:
        score = 0
    if has_forbidden_brackets(text):
        score += 100_000
    return score


def find_flagged_review_indices(reviews: list[dict]) -> list[int]:
    return [i for i, review in enumerate(reviews) if review_issue_score(review["content"]) > 0]


def regenerate_flagged_reviews(
    book: dict,
    reviews: list[dict],
    api_key: str,
    model: str,
    personas: list[dict],
    few_shot_example: dict,
) -> list[dict]:
    """분량 미달/초과 또는 금지 문장부호(『』「」)가 섞인 리뷰만 골라
    같은 페르소나/sentiment로 본문만 다시 쓴다.

    persona/sentiment는 그대로 고정한 채 content만 재생성하므로, 이 과정에서
    페르소나가 재배정되는 일이 없어 다른 리뷰와의 페르소나 중복이 발생할 수 없다.
    문제가 전혀 없는(점수 0) 결과가 나오면 즉시 채택하고, 끝까지 못 나오면
    그중 점수가 가장 낮은(가장 문제가 적은) 버전을 쓴다.
    """
    persona_by_name = {p["name"]: p for p in personas}

    for idx in find_flagged_review_indices(reviews):
        review = reviews[idx]
        persona = persona_by_name[review["persona"]]
        best_content = review["content"]
        accepted_content = None

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
                print(f"  [{review['persona']} 재생성 {attempt} 실패] {e}", file=sys.stderr)
                continue

            length = len(new_content)
            bracket_note = " [금지 문장부호 포함]" if has_forbidden_brackets(new_content) else ""
            print(
                f"  [{review['persona']} 재생성 {attempt}] {length}자{bracket_note} "
                f"(목표 {MIN_CONTENT_LENGTH}~{MAX_CONTENT_LENGTH}자)",
                file=sys.stderr,
            )

            if review_issue_score(new_content) == 0:
                accepted_content = new_content
                break

            if review_issue_score(new_content) < review_issue_score(best_content):
                best_content = new_content

        if accepted_content is not None:
            review["content"] = accepted_content
            continue

        remaining = []
        if len(best_content) < MIN_CONTENT_LENGTH:
            remaining.append(f"{MIN_CONTENT_LENGTH}자 미만({len(best_content)}자)")
        elif len(best_content) > MAX_CONTENT_LENGTH:
            remaining.append(f"{MAX_CONTENT_LENGTH}자 초과({len(best_content)}자)")
        if has_forbidden_brackets(best_content):
            remaining.append("금지 문장부호 포함")
        if remaining:
            print(
                f"  [경고] {review['persona']} 리뷰가 기준을 못 넘겨 최선 버전으로 저장됨: "
                f"{', '.join(remaining)}",
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

    return regenerate_flagged_reviews(book, reviews, api_key, model, personas, few_shot_example)


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
    raw_args = sys.argv[1:]
    force = "--force" in raw_args

    output_path = DEFAULT_OUTPUT_PATH
    if "--output" in raw_args:
        idx = raw_args.index("--output")
        if idx + 1 >= len(raw_args):
            print("--output 뒤에 파일명을 지정해야 합니다.", file=sys.stderr)
            sys.exit(1)
        output_path = PROCESSED_DIR / raw_args[idx + 1]
        raw_args = raw_args[:idx] + raw_args[idx + 2 :]

    args = [a for a in raw_args if not a.startswith("--")]

    if len(args) != 2:
        print(
            "사용법: python generate_llm_reviews.py <시작인덱스> <끝인덱스> "
            "[--force] [--output <파일명>]"
        )
        print("예시:   python generate_llm_reviews.py 0 87 --output llm_reviews_ver2.jsonl")
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
    processed_isbns = set() if force else load_processed_isbns(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

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

        with open(output_path, "a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        done += 1
        time.sleep(REQUEST_INTERVAL_SEC)

    print(
        f"\n[완료] {done}권 생성, {skipped}권 건너뜀, {len(failed)}권 실패 -> {output_path}",
        file=sys.stderr,
    )
    if failed:
        print(f"[실패 ISBN 목록] {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
