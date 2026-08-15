# Baseline 비교 평가 리포트

## 1. 개요

- **목적**: `random` / `popularity` / `aspect_based_model` 3개 모델을 동일 조건(pilot 데이터, K=5/10/20)으로 비교한다.
- **평가 데이터**: 팀원 4인 대상 1차 파일럿 `ML/eval/eval_data/eval_relevance.json`. n=4명짜리 pilot이라 통계적 유의성을 담보하지 않으며, 방향성(어느 모델이 낫다/못하다의 경향) 확인용으로만 본다.
- **평가 설정**: `EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)`, `relevant_threshold=2`(기본값). Recall/NDCG 계산 로직은 `ML/eval/evaluation.py`의 `evaluate_model()` 공용 코드를 그대로 사용.
- **비교 대상 모델**
  - `random`: `random_recommend_fn` (카탈로그 88권 무작위 셔플)
  - `popularity`: `ML/pipeline/baseline_popularity.py` — `data/processed/book_popularity_baseline.csv` 기반 정적 랭킹. 이 CSV는 교보문고 원본 베스트셀러 스냅샷 48개를 직접 집계해 산출한 것으로(`notebook/book_popularity_baseline.ipynb`), `score = raw_score / √중복횟수`(raw_score = Σ(1/스냅샷별 순위), 등장 기간에 제곱근 감쇠 적용) 공식을 쓴다. **`eval_relevance.json`과 완전히 무관한 독립 데이터**라 채점 정답지를 참조하지 않는다.
  - `aspect_based_model`: `ML/pipeline/aspect_based_model.py` (친구가 만든 추천 시스템, 리뷰 임베딩 클러스터링 + 유저 선호/기피 매칭)

> **변경 이력**: `popularity`는 처음에 `eval_relevance.json`(팀원 4명 relevance 평가)의 책별 평균을 대리 지표로 썼으나, 이는 채점 정답지를 그대로 베껴 쓰는 데이터 누수(circular evaluation)였다(구버전 결과는 4절 하단 참고). `data/processed/book_popularity_baseline.csv`(팀원이 원본 베스트셀러 데이터로 새로 산출)로 교체해 누수를 해소한 뒤의 결과가 아래 2~3절이다.

---

## 2. 전체(overall) 결과표

| model | Recall@5 | Recall@10 | Recall@20 | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---|---|---|---|---|---|
| random | 0.0584 | 0.1166 | 0.2326 | 0.3729 | 0.4006 | 0.4148 |
| popularity | 0.0511 | 0.1307 | 0.2763 | 0.2705 | 0.3724 | 0.4595 |
| aspect_based_model | 0.0991 | 0.1448 | 0.2687 | 0.6531 | 0.5695 | 0.5525 |

---

## 3. hasRead=true 서브셋 결과표

실제로 읽어본 책에 대한 평가만 걸러낸 서브셋 — 신뢰도가 더 높은 라벨로 본다.

| model | Recall@10 | NDCG@10 | n_users |
|---|---|---|---|
| random | 0.0000 | 0.0076 | 3 |
| popularity | 0.1032 | 0.0668 | 3 |
| aspect_based_model | 0.4365 | 0.3720 | 3 |

---

## 4. ⚠️ 알려진 한계

### 4.1 popularity의 카탈로그 커버리지 (88권 중 2권 누락)

`book_popularity_baseline.csv`는 교보문고 원본 베스트셀러 스냅샷 48개를 직접 집계한 것이라, 88권 카탈로그(`books_naver.jsonl`)와 isbn 기준으로 완벽히 일치하지 않는다.

- **`노르웨이의 숲`**: 48개 스냅샷 어디에도 등장 이력이 없어 인기도 CSV에 아예 없음.
- **`페스트`**: 카탈로그 isbn(`9788954638890`)과 다른 코드(`2090000163315`, 표준 ISBN 형식이 아님)로 인기도 CSV에 잘못 매칭돼 있어 카탈로그와 연결이 안 됨.

이 2권은 `popularity.recommend()`가 구조적으로 절대 추천할 수 없다(후보 자체에서 빠져 있음). 88권 중 2권(2.3%)이라 전체 지표에 미치는 영향은 제한적이지만, 이 두 책이 relevance가 높게 평가된 책이었다면 `popularity`의 Recall 상한이 그만큼 깎였을 수 있다. isbn 매핑 수정은 후속 작업으로 남겨둔다.

### 4.2 [해소됨, 기록용] 이전 버전의 데이터 누수 문제

`popularity`를 `eval_relevance.json` 평균으로 구현했던 구버전에서는 아래와 같이 비정상적으로 높은 점수가 나왔었다 — **채점 정답지를 인기도 계산에도 그대로 써서 생긴 누수**였다.

| model (구버전) | NDCG@5 | NDCG@10 | NDCG@20 |
|---|---|---|---|
| popularity (eval_relevance.json 평균, 누수 버전) | 0.8240 | 0.7878 | 0.7346 |

`book_popularity_baseline.csv`로 교체한 뒤(2~3절의 현재 값) 이 비정상적인 우위는 사라졌고, 오히려 NDCG@5 기준으로는 `random`(0.3729)보다도 낮게 나온다(0.2705) — 개인화되지 않은 일반적 인기 신호가 pilot 유저 개개인의 취향과는 잘 안 맞을 수 있음을 보여주는, 훨씬 상식적인 결과다.

---

## 5. 결론

- **`aspect_based_model`이 `random`, `popularity` 두 baseline보다 전반적으로 우수함을 확인했다.** 특히 NDCG@5(0.6531 vs random 0.3729, popularity 0.2705)와 `hasRead=true` 구간(NDCG@10 0.3720 vs random 0.0076, popularity 0.0668)에서 격차가 뚜렷하다.
- `popularity`(비개인화 베스트셀러 인기도)는 `random`보다도 뚜렷한 우위를 보이지 않는다(NDCG@5는 오히려 random보다 낮음) — 이는 88권 규모의 소카탈로그·pilot 4인이라는 조건에서, "일반적으로 잘 팔리는 책"과 "이 사람 개인의 취향에 맞는 책"이 크게 다를 수 있음을 시사한다.
- 이번 비교는 누수 없는 정당한 3자 비교이며, `aspect_based_model`의 우위가 `popularity` 대비로도 확인됐다는 점에서 이전(4.2절, popularity가 누수로 부풀려졌던 버전)보다 신뢰도 높은 결론이다.

---

## 6. 다음 단계

1. `popularity` 카탈로그 누락 2권(노르웨이의 숲, 페스트) isbn 매핑 수정
2. `data/processed/interactions.csv`(유저 좋아요/리뷰 로그) 확보 시, `popularity`에 실제 유저 행동 신호를 추가 반영할지 검토(현재는 베스트셀러 판매 데이터 기반)
3. 2차(production) 평가로 표본을 확대(팀원 4인 pilot → 실 서비스 유저)한 뒤 세 모델 재비교
