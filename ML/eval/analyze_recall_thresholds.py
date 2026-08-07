"""evaluation.py는 건드리지 않고, "relevant"로 인정하는 relevance 임계값을 다르게
잡았을 때 Recall@K가 어떻게 달라지는지 로컬에서만 비교한다.

evaluation.py의 evaluate_model()은 relevance>0을 relevant로 고정해서 채점하는데,
지금 데이터에서는 대부분의 책이 relevance>=1이라 Recall이 구조적으로 낮게(랜덤과
비슷하게) 나온다. recall_at_k() 함수 자체는 relevant_ids를 인자로 받아서 임계값에
무관하게 재사용 가능하므로, 여기서는 evaluate_model()을 거치지 않고 recall_at_k()를
직접 호출해 threshold=1(현재 채점 기준)/2/3을 비교한다.

사용법(ML/eval 폴더에서): uv run --project .. python analyze_recall_thresholds.py
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from aspect_based_model import recommend
from coldstart import load_book_descriptions
from evaluation import load_eval_relevance, load_eval_users, random_recommend_fn, recall_at_k

THRESHOLDS = [1, 2, 3]
KS = (5, 10, 20)


if __name__ == "__main__":
    eval_users = load_eval_users()
    eval_relevance = load_eval_relevance()
    book_ids = list(load_book_descriptions().keys())

    max_k = max(KS)
    random_fn = random_recommend_fn(book_ids, seed=42)

    # 유저마다 추천 결과를 한 번씩만 뽑아서 재사용 (evaluate_model()과 동일한 절약 방식)
    ours_recs = {uid: recommend(uid, max_k) for uid in eval_users}
    random_recs = {uid: random_fn(uid, max_k) for uid in eval_users}

    for threshold in THRESHOLDS:
        print(f"\n=== relevant 기준: relevance >= {threshold} ===")
        for label, recs in [("ours", ours_recs), ("random", random_recs)]:
            per_k_recalls = {k: [] for k in KS}
            n_users_used = 0
            for uid in eval_users:
                relevance_for_user = eval_relevance.get(uid, {})
                relevant_ids = {
                    bid
                    for bid, lb in relevance_for_user.items()
                    if lb.relevance is not None and lb.relevance >= threshold
                }
                if not relevant_ids:
                    continue
                n_users_used += 1
                for k in KS:
                    per_k_recalls[k].append(recall_at_k(recs[uid], relevant_ids, k))

            means = {k: statistics.fmean(v) if v else float("nan") for k, v in per_k_recalls.items()}
            print(
                f"  {label:<7} (n_users={n_users_used}): "
                + "  ".join(f"Recall@{k}={means[k]:.4f}" for k in KS)
            )
