"""인기도(popularity) 베이스라인 추천기 — DESIGN.md 3절 팀 공통 인터페이스를 만족한다.

개인화 없이 모든 유저에게 동일한 Top-K 인기 도서를 반환한다.

원래는 "좋아요 수 + 리뷰 수" 기반으로 설계하려 했으나, 실제 데이터를 확인한 결과:
- data/processed/interactions.csv(좋아요 로그)는 존재하지 않는다.
- data/processed/llm_reviews.jsonl은 책마다 정확히 5개(호 2 / 불호 2 / 혼재 1)로
  완전히 균일하게 생성되어 있어(generate_llm_reviews.py의 sentiment 배정 규칙),
  리뷰 수·sentiment 비율 어느 쪽도 책 간에 차이가 없다 — 88권이 전부 동점 처리됨.

[변경 이력] 처음에는 ML/eval/eval_data/eval_relevance.json(팀원 4명 relevance 평가)의
책별 평균을 인기도 대리 지표로 썼으나, 이 파일이 evaluate_model()의 채점 정답지와
동일해서 데이터 누수(circular evaluation)가 있었다 — popularity가 다른 모델보다
비정상적으로 높게 나오는 문제가 확인됨(ML/eval/eval_results/baseline_comparison_report.md
4절 참고). 대신 data/processed/book_popularity_baseline.csv(교보문고 원본 베스트셀러
스냅샷 48개에서 산출된, eval_relevance.json과 완전히 무관한 실제 인기도 데이터,
notebook/book_popularity_baseline.ipynb 참고)로 교체해 누수를 해소했다.

book_popularity_baseline.csv의 score 산출 공식(요약, 자세한 근거는 노트북 참고):
    score = raw_score / sqrt(중복횟수), raw_score = Σ(1/그 스냅샷에서의 순위)
등장 기간(중복횟수)에 제곱근 감쇠를 적용해, "오래 리스트에 남아있었던 것"이
"실제로 최상위였던 것"을 과도하게 압도하지 않도록 보정한 값이다.
"""

from __future__ import annotations

import csv
from pathlib import Path

DEFAULT_POPULARITY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "book_popularity_baseline.csv"
)


def load_popularity_ranking(
    path: str | Path = DEFAULT_POPULARITY_PATH,
) -> tuple[list[str], dict[str, float]]:
    """book_popularity_baseline.csv를 읽어 final_rank 순서의 book_id(=상품코드/isbn)
    리스트와 book_id -> score 매핑을 반환한다. 순위는 이미 노트북에서 계산돼 있으므로
    여기서는 다시 집계하지 않고 그대로 불러와 정렬만 보장한다.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda row: int(row["final_rank"]))
    ranking = [row["상품코드"] for row in rows]
    scores = {row["상품코드"]: float(row["score"]) for row in rows}
    return ranking, scores


# 모듈 로드 시 한 번만 로드 — recommend() 호출마다 파일을 다시 읽지 않는다.
_POPULARITY_RANKING, _POPULARITY_SCORES = load_popularity_ranking()


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
        print(f"  {rank}. {book_id}  score={_POPULARITY_SCORES[book_id]:.4f}")
