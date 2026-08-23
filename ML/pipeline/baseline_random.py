"""랜덤 베이스라인 추천기 — DESIGN.md 3절 팀 공통 인터페이스를 만족한다.

ML/eval/evaluation.py의 random_recommend_fn을 그대로 재사용해 book_id 88권 중
Top-K를 무작위로 반환한다. sanity check(하이퍼기하분포 이론값 대조)의 대상이 되는
가장 단순한 베이스라인.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ML/pipeline과 ML/eval은 별도 디렉토리라(패키지 구조 없음) sys.path에 eval/를
# 추가해서 임포트한다. data/src/llm_review처럼 같은 폴더 내 import 관례와 달리
# 폴더가 다르므로 필요.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from evaluation import RecommendFn, random_recommend_fn  # noqa: E402

DEFAULT_BOOKS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "books_naver.jsonl"
DEFAULT_SEED = 42


def load_book_ids(path: str | Path = DEFAULT_BOOKS_PATH) -> list[str]:
    """books_naver.jsonl 각 줄의 isbn을 book_id로 그대로 읽어 리스트로 반환."""
    book_ids = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            book_ids.append(json.loads(line)["isbn"])
    return book_ids


_recommend_fn_cache: RecommendFn | None = None


def _get_recommend_fn() -> RecommendFn:
    """최초 호출 시에만 book_ids 로드 + random_recommend_fn 생성, 이후 캐시 재사용."""
    global _recommend_fn_cache
    if _recommend_fn_cache is None:
        book_ids = load_book_ids()
        _recommend_fn_cache = random_recommend_fn(book_ids, seed=DEFAULT_SEED)
    return _recommend_fn_cache


def recommend(user_id: str, k: int = 10) -> list[str]:
    """팀 공통 인터페이스. user_id는 랜덤 추천에서 쓰이지 않지만 시그니처 통일을 위해 유지."""
    return _get_recommend_fn()(user_id, k)


if __name__ == "__main__":
    sample_user_id = "u_demo"
    k = 10
    recommendations = recommend(sample_user_id, k=k)
    print(f"카탈로그 크기: {len(load_book_ids())}권")
    print(f"recommend({sample_user_id!r}, k={k}) -> {len(recommendations)}권")
    print(recommendations)
