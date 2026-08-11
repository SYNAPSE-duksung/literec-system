"""팀원 4명이 구글폼으로 응답한 실제 eval_users.json/eval_relevance.json으로
aspect_based_model.recommend()를 채점한다.

pipeline/verify_evaluate_integration.py가 synthetic(자기 자신의 추천 결과를
정답으로 삼은) 라벨로 "배선만" 확인했던 것과 달리, 이 스크립트는 진짜 팀원
데이터로 실제 Recall@K/NDCG@K를 낸다.

사용법(ML/eval 폴더에서): uv run --project .. python run_real_evaluation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))

from aspect_based_model import recommend
from evaluation import (
    EvalConfig,
    evaluate_model,
    load_eval_relevance,
    load_eval_users,
    print_report,
    save_report,
)

if __name__ == "__main__":
    eval_users = load_eval_users()
    eval_relevance = load_eval_relevance()

    n_labels = sum(len(v) for v in eval_relevance.values())
    print(f"평가 유저 {len(eval_users)}명, relevance 레코드 {n_labels}건\n")

    config = EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)
    report = evaluate_model(
        recommend_fn=recommend,
        eval_users=eval_users,
        eval_relevance=eval_relevance,
        config=config,
        model_name="aspect_based_model",
    )
    print_report(report)

    saved_path = save_report(report)
    print(f"\n저장 완료: {saved_path}")
