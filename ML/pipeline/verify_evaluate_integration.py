"""aspect_based_model.py의 recommend()가 ML/eval/evaluation.py의 evaluate_model()에
실제로 꽂히는지 확인하는 통합 테스트 스크립트.

실제 eval_users.json/eval_relevance.json이 아직 존재하지 않으므로(팀원 쪽도 동일한
상태 - evaluation.py 자체도 synthetic 데이터로 self-check함), 여기서는:
  - eval_users: mock_data/user_profiles.json(u001~u004)을 EvalUser로 변환
  - eval_relevance: 진짜 정답 라벨이 없으므로, recommend()가 실제로 반환하는 실제
    카탈로그(isbn)의 책 몇 권에 임의로 relevance를 부여한 synthetic 라벨
이 두 개를 만들어 evaluate_model()에 넘긴다. 목적은 "점수가 좋냐"가 아니라
"인터페이스가 정확히 맞물려서 에러 없이 Recall/NDCG가 계산되냐"를 확인하는 것.

사용법(ML 폴더에서): uv run python pipeline/verify_evaluate_integration.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))

from aspect_based_model import DEFAULT_USER_RECORDS_PATH, recommend
from evaluation import (
    EvalConfig,
    EvalUser,
    RelevanceLabel,
    evaluate_model,
    print_report,
)

if __name__ == "__main__":
    with open(DEFAULT_USER_RECORDS_PATH, encoding="utf-8") as f:
        raw_users = json.load(f)

    eval_users = {
        u["userId"]: EvalUser(
            user_id=u["userId"],
            preferred_emotions=u["preferredEmotions"],
            avoided_traits=u["avoidedTraits"],
        )
        for u in raw_users
    }

    print("=== 1. recommend()가 evaluate_model() 없이 단독으로 잘 도는지 먼저 확인 ===")
    for user_id in eval_users:
        result = recommend(user_id, k=20)
        print(f"  [{user_id}] Top-20 중 처음 3개: {result[:3]} (총 {len(result)}개)")

    print("\n=== 2. synthetic relevance 라벨 생성 (recommend() 결과의 일부에 임의 부여) ===")
    eval_relevance: dict[str, dict[str, RelevanceLabel]] = {}
    for user_id in eval_users:
        recommended = recommend(user_id, k=20)
        # 실제 정답이 없으므로: 추천된 것 중 1~3번째는 relevant(3/2/1), 10번째는
        # 비관련(0)이라고 가정한 라벨을 임의로 붙인다 (진짜 정답 라벨이 오면 이 블록만
        # load_eval_relevance()로 교체하면 됨).
        eval_relevance[user_id] = {
            recommended[0]: RelevanceLabel(relevance=3, has_read=False, label_source="aspect_card"),
            recommended[1]: RelevanceLabel(relevance=2, has_read=False, label_source="aspect_card"),
            recommended[2]: RelevanceLabel(relevance=1, has_read=True, label_source="read"),
            recommended[9]: RelevanceLabel(relevance=0, has_read=False, label_source="aspect_card"),
        }
        print(f"  [{user_id}] relevance 부여: {list(eval_relevance[user_id].keys())}")

    print("\n=== 3. evaluate_model()로 실제 채점 ===")
    config = EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)
    report = evaluate_model(
        recommend_fn=recommend,
        eval_users=eval_users,
        eval_relevance=eval_relevance,
        config=config,
        model_name="aspect_based_model",
    )
    print_report(report)

    print("\n[통합 테스트 통과] recommend()가 evaluate_model()에 에러 없이 꽂혔습니다.")
    print("(주의: 위 Recall/NDCG는 synthetic 라벨 기준이라 실제 모델 품질을 의미하지 않음 -")
    print(" 실제 eval_relevance.json이 생기면 이 스크립트의 2번 블록만 교체할 것)")
