"""Phase 4 기피 페널티 가중치 λ를 실제 팀원 4명 pilot 데이터로 그리드서치한다.

DESIGN.md 7절: "Phase 4 기피 페널티 가중치 λ 최종값 (mock 데이터로 실험, 기본값
0.5부터 시작)" - 이 스크립트로 실 데이터 기준 1차 점검을 한다.

n=4명짜리 pilot이라 "완벽한 최적값"을 확정하기보다 "0.5가 나쁘지 않은 선택인지,
아니면 확실히 더 나은 값이 있는지" 정도의 1차 신호로만 본다 - 팀원의 relevance
데이터가 더 쌓이면 재검토가 필요하다.

recommend()의 시그니처(DESIGN.md 3절 인터페이스)는 그대로 두고, 이 스크립트는
aspect_based_model의 내부 빌딩 블록(build_catalog/build_user_profile_index/_score)을
직접 가져다 써서 λ만 바꿔가며 평가한다 - 무거운 연산(카탈로그 생성)은 1번만 하고
λ 스윕 자체는 순수 벡터 연산이라 빠르다.

사용법(ML/eval 폴더에서): uv run --project .. python tune_lambda.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from aspect_based_model import _score, build_catalog, build_user_profile_index
from evaluation import EvalConfig, evaluate_model, load_eval_relevance, load_eval_users

LAMBDA_GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]


def make_recommend_fn(catalog, profiles, lam):
    def _recommend(user_id: str, k: int = 10) -> list[str]:
        profile = profiles.get(user_id)
        if profile is None:
            return []
        scored = [(book_id, _score(profile, vectors, lam)) for book_id, vectors in catalog.items()]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [book_id for book_id, _ in scored[:k]]

    return _recommend


if __name__ == "__main__":
    eval_users = load_eval_users()
    eval_relevance = load_eval_relevance()

    print("카탈로그/유저 프로필 빌드 중 (1회만 실행)...")
    catalog = build_catalog()
    profiles = build_user_profile_index()

    config = EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)

    print(f"\n{'lambda':>8}  {'NDCG@5':>8}  {'NDCG@10':>8}  {'NDCG@20':>8}  {'Recall@10':>10}")
    best_lambda, best_ndcg10 = None, -1.0
    for lam in LAMBDA_GRID:
        recommend_fn = make_recommend_fn(catalog, profiles, lam)
        report = evaluate_model(
            recommend_fn=recommend_fn,
            eval_users=eval_users,
            eval_relevance=eval_relevance,
            config=config,
            model_name=f"lambda={lam}",
        )
        m = report.metrics["overall"]
        print(
            f"{lam:>8.2f}  {m[5]['ndcg']:>8.4f}  {m[10]['ndcg']:>8.4f}  "
            f"{m[20]['ndcg']:>8.4f}  {m[10]['recall']:>10.4f}"
        )
        if m[10]["ndcg"] > best_ndcg10:
            best_lambda, best_ndcg10 = lam, m[10]["ndcg"]

    print(f"\n[결과] NDCG@10 기준 최선의 lambda = {best_lambda} (NDCG@10={best_ndcg10:.4f})")
    print("(참고: n=4명 pilot이라 확정값이 아니라 1차 신호로만 볼 것)")
