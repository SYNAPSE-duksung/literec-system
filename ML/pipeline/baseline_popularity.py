"""인기도(popularity) 베이스라인 추천기 — DESIGN.md 3절 팀 공통 인터페이스를 만족한다.

개인화 없이 모든 유저에게 동일한 Top-K 인기 도서를 반환한다.

원래는 "좋아요 수 + 리뷰 수" 기반으로 설계하려 했으나, 실제 데이터를 확인한 결과:
- data/processed/interactions.csv(좋아요 로그)는 존재하지 않는다.
- data/processed/llm_reviews.jsonl은 책마다 정확히 5개(호 2 / 불호 2 / 혼재 1)로
  완전히 균일하게 생성되어 있어(generate_llm_reviews.py의 sentiment 배정 규칙),
  리뷰 수·sentiment 비율 어느 쪽도 책 간에 차이가 없다 — 88권이 전부 동점 처리됨.

대신 ML/eval/eval_data/eval_relevance.json(팀원 4명이 남긴 실제 0~3 relevance 평가)의
책별 평균 점수를 인기도 대리 지표로 쓴다. 합산이 아니라 평균을 쓰는 이유: 책마다 평가한
유저 수가 3~4명으로 달라서, 합산하면 평가받은 횟수가 많은 책이 구조적으로 유리해지는
편향이 생기기 때문이다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from evaluation import RelevanceLabel, load_eval_relevance  # noqa: E402


def compute_popularity_scores(
    eval_relevance: dict[str, dict[str, RelevanceLabel]],
) -> dict[str, float]:
    """책(isbn=book_id)별 relevance 평균을 인기도 점수로 계산.

    평균을 쓰는 이유: 책마다 평가한 유저 수가 달라 합산하면 평가받은 횟수가 많은
    책이 구조적으로 유리해지기 때문(모듈 docstring 참고).
    """
    scores_by_book: dict[str, list[int]] = {}
    for user_relevance in eval_relevance.values():
        for book_id, label in user_relevance.items():
            if label.relevance is not None:
                scores_by_book.setdefault(book_id, []).append(label.relevance)
    return {book_id: sum(values) / len(values) for book_id, values in scores_by_book.items()}


def compute_popularity_ranking(scores: dict[str, float]) -> list[str]:
    """평균 relevance 내림차순, 동점 시 book_id 오름차순으로 정렬한 book_id 리스트."""
    return sorted(scores, key=lambda book_id: (-scores[book_id], book_id))


# 모듈 로드 시 한 번만 계산 — recommend() 호출마다 다시 집계하지 않는다.
_POPULARITY_SCORES: dict[str, float] = compute_popularity_scores(load_eval_relevance())
_POPULARITY_RANKING: list[str] = compute_popularity_ranking(_POPULARITY_SCORES)


def recommend(user_id: str, k: int = 10) -> list[str]:
    """user_id를 받아 book_id Top-K 추천 리스트 반환 (DESIGN.md 3절 인터페이스).

    개인화 없음 — user_id는 인기도 로직에 영향을 주지 않고, 시그니처 통일을 위해서만 유지.
    """
    return _POPULARITY_RANKING[:k]


if __name__ == "__main__":
    print(f"인기도 집계 대상: {len(_POPULARITY_RANKING)}권\n")

    sample_user_id = "아무_user_id"
    k = 10
    result = recommend(sample_user_id, k=k)
    print(f"recommend({sample_user_id!r}, k={k}) 결과:")
    for rank, book_id in enumerate(result, start=1):
        print(f"  {rank}. {book_id}  평균 relevance={_POPULARITY_SCORES[book_id]:.2f}")
