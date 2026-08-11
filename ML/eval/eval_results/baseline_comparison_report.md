# Baseline 비교 평가 리포트

## 1. 개요

- **목적**: `random` / `popularity` / `aspect_based_model` 3개 모델을 동일 조건(pilot 데이터, K=5/10/20)으로 비교한다.
- **평가 데이터**: 팀원 4인 대상 1차 파일럿 `ML/eval/eval_data/eval_relevance.json`. n=4명짜리 pilot이라 통계적 유의성을 담보하지 않으며, 방향성(어느 모델이 낫다/못하다의 경향) 확인용으로만 본다.
- **평가 설정**: `EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)`, `relevant_threshold=2`(기본값). Recall/NDCG 계산 로직은 `ML/eval/evaluation.py`의 `evaluate_model()` 공용 코드를 그대로 사용.
- **비교 대상 모델**
  - `random`: `random_recommend_fn` (카탈로그 88권 무작위 셔플)
  - `popularity`: `ML/pipeline/baseline_popularity.py` (책별 relevance 평균 기반 정적 랭킹)
  - `aspect_based_model`: `ML/pipeline/aspect_based_model.py` (친구가 만든 추천 시스템, 리뷰 임베딩 클러스터링 + 유저 선호/기피 매칭)

---

## 2. 전체(overall) 결과표

| model | Recall@5 | Recall@10 | Recall@20 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---|---|---|---|---|---|
| random | 0.0584 | 0.1166 | 0.2326 | 0.3729 | 0.4006 | 0.4148 |
| popularity | 0.0966 | 0.1888 | 0.3486 | 0.8240 | 0.7878 | 0.7346 |
| aspect_based_model | 0.0794 | 0.1448 | 0.2641 | 0.6105 | 0.5510 | 0.5329 |

---

## 3. hasRead=true 서브셋 결과표

실제로 읽어본 책에 대한 평가만 걸러낸 서브셋 — 신뢰도가 더 높은 라벨로 본다.

| model | Recall@10 | NDCG@10 | n_users |
|---|---|---|---|
| random | 0.0000 | 0.0076 | 3 |
| popularity | 0.2222 | 0.1425 | 3 |
| aspect_based_model | 0.4365 | 0.3082 | 3 |

---

## 4. ⚠️ 알려진 한계

**`popularity` baseline은 채점용 정답지를 인기도 계산에도 그대로 쓰고 있어 데이터 누수(leakage)가 있다.**

`baseline_popularity.py`의 `recommend()`는 `ML/eval/eval_data/eval_relevance.json`(=이 리포트의 채점 기준이 되는 정답 라벨)의 책별 평균 relevance를 그대로 정렬해 추천 순위를 만든다. 즉 "정답지를 보고 정답 순서대로 답을 제출"하는 구조라, 같은 `eval_relevance.json`으로 다시 채점하면 점수가 비정상적으로 높게 나올 수밖에 없다.

- **증거**: `popularity`의 overall NDCG@5 = **0.8240**은 거의 만점에 가까운 수치로, 정상적인 held-out 평가에서 나올 수 있는 값이 아니다. 이는 실제 추천 품질이 아니라 순환 평가(circular evaluation)의 산물이다.
- 따라서 **`popularity`의 overall 지표는 참고용으로만** 사용하고, 다른 모델과의 직접적인 우열 비교에는 쓰지 않는다.
- 반면 `random`은 `eval_relevance.json`을 전혀 참조하지 않고(순수 무작위), `aspect_based_model`도 `eval_users.json`(온보딩 선호/기피)과 리뷰 임베딩만 사용할 뿐 `eval_relevance.json`을 입력으로 쓰지 않는다 — 두 모델의 점수는 정상적인 held-out 평가다.
- **실질적으로 공정한 비교는 `random` vs `aspect_based_model`**이며, `hasRead=true` 서브셋(NDCG@10 기준: random=0.0076, popularity=0.1425, aspect_based_model=**0.3082**)에서 `aspect_based_model`이 `random`과 `popularity` 둘 다 상회함을 확인했다. `popularity`가 이 구간에서도 여전히 `eval_relevance.json`(hasRead=true 라벨 포함)을 그대로 참조하고 있어 이 비교조차 `popularity`에게 완전히 불리하지 않은데도, `aspect_based_model`이 더 높게 나온 것은 의미 있는 신호다.
- **2차 평가(`data/processed/interactions.csv` 확보 후)에서 `popularity` baseline을 원안(좋아요 수 + 리뷰 수 집계) 방식대로 재구현할 예정이다.** 현재 버전은 `interactions.csv`(좋아요/리뷰 로그)가 아직 없어 `eval_relevance.json`으로 대체 구현한 임시 버전임을 명시한다.

---

## 5. 결론

- **현재 시점 결론**: `aspect_based_model`이 `random` baseline보다 명확히 우수함을 확인했다. 특히 `hasRead=true` 구간(신뢰도 높은 라벨)에서 격차가 뚜렷하다(NDCG@10 기준 +0.3006, random 대비 약 40배).
- `popularity`와의 비교는 위 4절의 데이터 누수 문제로 인해 이번 pilot에서는 공정한 결론을 내릴 수 없다 — **2차 평가에서 재검증이 필요**하다.

---

## 6. 다음 단계

1. `data/processed/interactions.csv`(유저 좋아요/리뷰 로그) 확보 후 `popularity` baseline을 원안(좋아요 수 + 리뷰 수 집계)대로 재구현
2. 2차(production) 평가로 표본을 확대(팀원 4인 pilot → 실 서비스 유저)한 뒤 세 모델 재비교
