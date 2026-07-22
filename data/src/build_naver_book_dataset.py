"""
final_book_list_88.csv의 도서를 네이버 도서검색 API(book_adv)로 재조회하여
title/image/author/publisher/description을 새로 구축하고 JSONL로 저장한다.

- ISBN은 CSV의 `상품코드` 컬럼 값을 사용한다. (`판매상품 ID`는 교보문고 내부 상품 ID이며 ISBN이 아니다)
- perplexity 검색 결과는 이 단계에서는 비워두고 이후 별도 파이프라인에서 채운다.
"""

import csv
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

CSV_PATH = Path(__file__).parent.parent / "processed" / "final_book_list_88.csv"
OUTPUT_PATH = Path(__file__).parent.parent / "processed" / "books_naver.jsonl"
ENV_PATH = Path(__file__).parent.parent / ".env"

NAVER_API_URL = "https://openapi.naver.com/v1/search/book_adv.json"
REQUEST_INTERVAL_SEC = 0.2
MAX_RETRIES = 3

TAG_RE = re.compile(r"</?b>")


def load_books(csv_path: Path) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean_text(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value)).strip()


def fetch_naver_book(isbn: str, client_id: str, client_secret: str) -> dict | None:
    query = urllib.parse.urlencode({"d_isbn": isbn, "display": 1})
    request = urllib.request.Request(
        f"{NAVER_API_URL}?{query}",
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.load(response)
            items = body.get("items", [])
            return items[0] if items else None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                time.sleep(1.0 * attempt)
                continue
            print(f"  [실패] ISBN {isbn}: HTTP {e.code}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"  [실패] ISBN {isbn}: {e}", file=sys.stderr)
            return None

    return None


def build_record(book: dict, naver_item: dict | None) -> dict:
    record = {
        "isbn": book["상품코드"],
        "product_id": book["판매상품 ID"],
        "title": "",
        "image": "",
        "author": "",
        "publisher": "",
        "description": "",
        "perplexity_review": None,
    }
    if naver_item:
        record["title"] = clean_text(naver_item.get("title", ""))
        record["image"] = naver_item.get("image", "")
        record["author"] = clean_text(naver_item.get("author", ""))
        record["publisher"] = clean_text(naver_item.get("publisher", ""))
        record["description"] = clean_text(naver_item.get("description", ""))
    return record


def main():
    load_dotenv(ENV_PATH)
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("data/.env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 없습니다.", file=sys.stderr)
        sys.exit(1)

    books = load_books(CSV_PATH)
    records = []
    failed_isbns = []

    for i, book in enumerate(books):
        isbn = book["상품코드"]
        print(f"[{i + 1}/{len(books)}] {book['상품명']} (ISBN {isbn})", file=sys.stderr)

        naver_item = fetch_naver_book(isbn, client_id, client_secret)
        if naver_item is None:
            failed_isbns.append(isbn)

        records.append(build_record(book, naver_item))
        time.sleep(REQUEST_INTERVAL_SEC)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(
        f"\n[완료] {len(records)}건 저장 -> {OUTPUT_PATH} "
        f"(검색 실패 {len(failed_isbns)}건)",
        file=sys.stderr,
    )
    if failed_isbns:
        print(f"[실패 ISBN 목록] {failed_isbns}", file=sys.stderr)


if __name__ == "__main__":
    main()
