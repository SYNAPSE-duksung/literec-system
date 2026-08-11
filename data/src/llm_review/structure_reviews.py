"""
data/processed/llm_reviews.jsonl(팀원이 생성한 페르소나 리뷰 원문)을 책 단위로 묶어서
Upstage Solar API에 넘기고, 5축 스키마(정서_경험/좋았던_요소/별로였던_요소/소재_및_주제/
독서_경험_맥락)로 구조화한 결과를 data/processed/structured_reviews.jsonl에 한 줄씩
append한다.

ML/pipeline/DESIGN.md 2절 스키마를 그대로 따른다:
  - book_id = isbn, review_id = f"{isbn}_{review_index}"
  - meta.label은 원본 리뷰의 sentiment 값을 그대로 복사한다 (여기서 새로 판단하지 않음)
  - 5축 중 언급이 없는 축은 null로 둔다 (없는 내용을 지어내지 않음)

책 한 권(리뷰 5개)을 한 번의 API 호출로 같이 구조화한다 - 리뷰 낱개로 호출하면 440번
호출해야 하지만, 책 단위로 묶으면 88번으로 줄어든다.

사용법(data 폴더에 들어와서):
  uv run python src/llm_review/structure_reviews.py 0 0        # 인덱스 0번 책만
  uv run python src/llm_review/structure_reviews.py 0 87       # 전체
  uv run python src/llm_review/structure_reviews.py 0 87 --force  # 이미 처리된 isbn도 재처리
  uv run python src/llm_review/structure_reviews.py 0 87 --output structured_reviews_ver2.jsonl

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

from prompt_builder import build_structure_prompt

PROCESSED_DIR = Path(__file__).parent.parent.parent / "processed"
INPUT_PATH = PROCESSED_DIR / "llm_reviews.jsonl"
DEFAULT_OUTPUT_PATH = PROCESSED_DIR / "structured_reviews.jsonl"
ENV_PATH = Path(__file__).parent.parent.parent / ".env"

UPSTAGE_API_URL = "https://api.upstage.ai/v1/chat/completions"
DEFAULT_MODEL = "solar-pro3-260323"

REQUEST_INTERVAL_SEC = 1.0
MAX_RETRIES = 3
MAX_VALIDATION_RETRIES = 3
REQUEST_TIMEOUT_SEC = 120

AXES = ["정서_경험", "좋았던_요소", "별로였던_요소", "소재_및_주제", "독서_경험_맥락"]

CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def load_reviews_by_book(jsonl_path: Path) -> list[list[dict]]:
    """isbn별로 리뷰를 묶어, 파일에 처음 등장한 순서대로 책 리스트를 만든다."""
    books: dict[str, list[dict]] = {}
    for line in open(jsonl_path, encoding="utf-8"):
        review = json.loads(line)
        books.setdefault(review["isbn"], []).append(review)
    return list(books.values())


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


def parse_structured(raw_content: str) -> list[dict]:
    cleaned = CODE_FENCE_RE.sub("", raw_content).strip()
    data = json.loads(cleaned)
    return data["reviews"]


def validate_structured(structured: list[dict], expected_indices: set[int]) -> list[str]:
    """치명적 오류만 검증한다: 개수, review_index 누락/중복, 5축 전부 null인 리뷰."""
    issues = []

    if len(structured) != len(expected_indices):
        issues.append(f"리뷰 개수가 {len(expected_indices)}개가 아님: {len(structured)}개")
        return issues

    seen_indices = set()
    for item in structured:
        idx = item.get("review_index")
        if idx in seen_indices:
            issues.append(f"review_index 중복: {idx}")
        seen_indices.add(idx)

        if all(item.get(axis) is None for axis in AXES):
            issues.append(f"review_index {idx}: 5축이 전부 null임")

    if seen_indices != expected_indices:
        issues.append(f"review_index 불일치: 기대 {expected_indices}, 실제 {seen_indices}")

    return issues


def structure_book_with_retry(reviews: list[dict], api_key: str, model: str) -> list[dict]:
    prompt = build_structure_prompt(reviews)
    expected_indices = {r["review_index"] for r in reviews}
    current_prompt = prompt

    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        raw_content = call_upstage(current_prompt, api_key, model)
        structured = parse_structured(raw_content)
        issues = validate_structured(structured, expected_indices)
        if not issues:
            return structured
        print(f"  [검증 재시도 {attempt}] {issues}", file=sys.stderr)
        issue_text = "\n".join(f"- {issue}" for issue in issues)
        current_prompt = (
            f"{prompt}\n\n"
            f"[이전 시도의 문제점 - 이번엔 반드시 고쳐서 다시 작성할 것]\n{issue_text}"
        )

    raise RuntimeError(f"구조화 검증을 통과하지 못해 포기함(저장하지 않음): {issues}")


def build_output_records(reviews: list[dict], structured: list[dict]) -> list[dict]:
    structured_by_index = {item["review_index"]: item for item in structured}
    records = []
    for review in reviews:
        item = structured_by_index[review["review_index"]]
        records.append(
            {
                "book_id": review["isbn"],
                "review_id": f"{review['isbn']}_{review['review_index']}",
                "정서_경험": item.get("정서_경험"),
                "좋았던_요소": item.get("좋았던_요소"),
                "별로였던_요소": item.get("별로였던_요소"),
                "소재_및_주제": item.get("소재_및_주제"),
                "독서_경험_맥락": item.get("독서_경험_맥락"),
                "meta": {"label": review["sentiment"]},
            }
        )
    return records


def load_processed_book_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    with open(output_path, encoding="utf-8") as f:
        return {json.loads(line)["book_id"] for line in f if line.strip()}


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
            "사용법: python structure_reviews.py <시작인덱스> <끝인덱스> "
            "[--force] [--output <파일명>]"
        )
        print("예시:   python structure_reviews.py 0 87")
        sys.exit(1)

    start, end = int(args[0]), int(args[1])

    load_dotenv(ENV_PATH)
    api_key = os.environ.get("UPSTAGE_API_KEY")
    if not api_key:
        print("data/.env에 UPSTAGE_API_KEY가 없습니다.", file=sys.stderr)
        sys.exit(1)
    model = os.environ.get("UPSTAGE_MODEL", DEFAULT_MODEL)

    books = load_reviews_by_book(INPUT_PATH)
    if not (0 <= start <= end < len(books)):
        raise ValueError(f"인덱스 범위가 올바르지 않습니다. (0 ~ {len(books) - 1} 사이여야 함)")

    processed_book_ids = set() if force else load_processed_book_ids(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    done, skipped, failed = 0, 0, []
    for i in range(start, end + 1):
        reviews = books[i]
        isbn = reviews[0]["isbn"]
        title = reviews[0]["book_title"]

        if isbn in processed_book_ids:
            print(f"[{i}] {title} (ISBN {isbn}) - 이미 처리됨, 건너뜀", file=sys.stderr)
            skipped += 1
            continue

        print(f"[{i}] {title} (ISBN {isbn}) - 구조화 중...", file=sys.stderr)
        try:
            structured = structure_book_with_retry(reviews, api_key, model)
            records = build_output_records(reviews, structured)
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
        f"\n[완료] {done}권 구조화, {skipped}권 건너뜀, {len(failed)}권 실패 -> {output_path}",
        file=sys.stderr,
    )
    if failed:
        print(f"[실패 ISBN 목록] {failed}", file=sys.stderr)


if __name__ == "__main__":
    main()
