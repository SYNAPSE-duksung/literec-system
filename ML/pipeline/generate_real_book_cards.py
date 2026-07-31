"""실 데이터(88권, 440개 구조화 리뷰)로 Phase 2.5 책 카드를 생성해
ML/eval/eval_data/book_cards.json에 저장한다.

DESIGN.md가 예시로 든 저장 위치 그대로다. 이전에는 Phase 2 알고리즘(HDBSCAN)이
아직 미확정이라 실 데이터로 카드를 만들면 대부분 비어있을 것으로 예상돼 미뤘는데,
KMeans(n_clusters=30) + 캐치올 제외로 팀 확정된 뒤라 지금 생성한다.

사용법(ML 폴더에서): uv run python pipeline/generate_real_book_cards.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clustering import compute_book_identities, global_cluster
from embedding import embed_reviews
from xai import build_all_book_cards, build_review_embedding_index, save_book_cards

DATA_PROCESSED_DIR = Path(__file__).parent.parent.parent / "data" / "processed"
STRUCTURED_REVIEWS_PATH = DATA_PROCESSED_DIR / "structured_reviews.jsonl"
BOOKS_NAVER_PATH = DATA_PROCESSED_DIR / "books_naver.jsonl"
OUTPUT_PATH = Path(__file__).parent.parent / "eval" / "eval_data" / "book_cards.json"


def _load_reviews() -> list[dict]:
    reviews = []
    with open(STRUCTURED_REVIEWS_PATH, encoding="utf-8") as f:
        for line in f:
            reviews.append(json.loads(line))
    return reviews


def _load_title_map() -> dict[str, str]:
    title_map = {}
    with open(BOOKS_NAVER_PATH, encoding="utf-8") as f:
        for line in f:
            book = json.loads(line)
            title_map[book["isbn"]] = book["title"]
    return title_map


if __name__ == "__main__":
    reviews = _load_reviews()
    review_ids = [r["review_id"] for r in reviews]
    book_ids = [r["book_id"] for r in reviews]
    reviews_by_id = {r["review_id"]: r for r in reviews}

    print(f"입력 리뷰 {len(reviews)}개, 책 {len(set(book_ids))}권")

    _, embeddings = embed_reviews(reviews)
    review_embeddings = build_review_embedding_index(review_ids, embeddings)

    # 기본값 그대로 사용 (n_clusters=30, max_facets=2, coverage_threshold=0.3 - 팀 확정값)
    cluster_result = global_cluster(review_ids, book_ids, embeddings)
    book_identities = compute_book_identities(cluster_result)

    cards = build_all_book_cards(book_identities, cluster_result, review_embeddings, reviews_by_id)

    title_map = _load_title_map()
    for card in cards:
        card["title"] = title_map.get(card["book_id"], "")

    empty_cards = [c["book_id"] for c in cards if not c["facets"]]
    print(f"카드 생성 완료: {len(cards)}권 (결이 0개인 책: {len(empty_cards)}권)")
    if empty_cards:
        print(f"  결 0개 책 목록: {empty_cards}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_book_cards(OUTPUT_PATH, cards)
    print(f"저장 완료: {OUTPUT_PATH}")
