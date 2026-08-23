"""aspect_based_model.recommend()를 무작위 추천(random_recommend_fn)과 나란히
같은 실제 eval_users.json/eval_relevance.json으로 채점해, 우리 모델이 무작위보다
실제로 나은지 확인한다.

사용법(ML/eval 폴더에서): uv run --project .. python compare_vs_random.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from aspect_based_model import recommend
from coldstart import load_book_descriptions
from evaluation import (
    EvalConfig,
    evaluate_model,
    load_eval_relevance,
    load_eval_users,
    print_report,
    random_recommend_fn,
)

if __name__ == "__main__":
    eval_users = load_eval_users()
    eval_relevance = load_eval_relevance()

    # 랜덤 베이스라인이 뽑을 후보 풀(카탈로그의 book_id 전체)을 우리 모델과 동일하게 맞춘다.
    # build_catalog()를 다시 부르면 임베딩/클러스터링이 중복 실행되므로, 대신 책 목록만
    # 가볍게 가져온다(recommend()가 내부적으로 쓰는 카탈로그와 book_id 전체 집합은 동일).
    book_ids = list(load_book_descriptions().keys())

    config = EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)

    print("=== 1. aspect_based_model ===")
    ours_report = evaluate_model(
        recommend_fn=recommend,
        eval_users=eval_users,
        eval_relevance=eval_relevance,
        config=config,
        model_name="aspect_based_model",
    )
    print_report(ours_report)

    print("\n=== 2. 랜덤 베이스라인 ===")
    random_fn = random_recommend_fn(book_ids, seed=config.seed)
    random_report = evaluate_model(
        recommend_fn=random_fn,
        eval_users=eval_users,
        eval_relevance=eval_relevance,
        config=config,
        model_name="random_baseline",
    )
    print_report(random_report)

    print("\n=== 3. 비교 (전체 기준) ===")
    for k in config.ks:
        ours = ours_report.metrics["overall"][k]
        rand = random_report.metrics["overall"][k]
        print(
            f"  k={k:<3} Recall  ours={ours['recall']:.4f}  random={rand['recall']:.4f}  "
            f"(+{(ours['recall'] - rand['recall']):.4f})"
        )
        print(
            f"        NDCG    ours={ours['ndcg']:.4f}  random={rand['ndcg']:.4f}  "
            f"(+{(ours['ndcg'] - rand['ndcg']):.4f})"
        )
