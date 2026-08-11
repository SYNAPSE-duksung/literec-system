"""추천 모델 오프라인 평가 공용 코드 (DESIGN.md 3절 인터페이스 기준).

recommend(user_id: str, k: int = 10) -> list[str] 형태의 모델을 Recall@K / NDCG@K
(K=5,10,20)로 평가한다. Relevance는 0~3 graded + null(평가 제외)이며, Recall@K는
relevance >= EvalConfig.relevant_threshold(기본값 2, 팀 논의로 확정 - 기존
relevance>0 기준은 pilot 데이터에서 너무 후해 Recall이 무작위 추천과 잘 안
갈렸음)를 relevant로 간주해 계산한다. NDCG는 이 임계값과 무관하게 항상 등급을
그대로 쓴다.

eval_users.json/eval_relevance.json 스키마는 팀 확인을 거친 실제 형식(camelCase,
book 식별자는 isbn)을 따른다 — 자세한 필드 매핑은 load_eval_users/load_eval_relevance
docstring 참고.

"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

RecommendFn = Callable[[str, int], list[str]]
Subset = Literal["overall", "has_read_true", "has_read_false"]

EVAL_DIR = Path(__file__).parent
EVAL_DATA_DIR = EVAL_DIR / "eval_data"
RESULTS_DIR = EVAL_DIR / "eval_results"

DEFAULT_INTERACTIONS_PATH = EVAL_DIR.parent.parent / "data" / "processed" / "interactions.csv"
DEFAULT_EVAL_USERS_PATH = EVAL_DATA_DIR / "eval_users.json"
DEFAULT_EVAL_RELEVANCE_PATH = EVAL_DATA_DIR / "eval_relevance.json"


# ── 1. 타입/데이터 정의 ──────────────────────────────────────────


@dataclass(frozen=True)
class RelevanceLabel:
    relevance: int | None  # 0~3, None = 평가 제외("모르겠음")
    has_read: bool
    label_source: str | None = None  # "aspect_card" | "read" — hasRead와 1:1 대응 아님, 독립 저장


@dataclass(frozen=True)
class EvalUser:
    user_id: str
    preferred_emotions: list[str]
    avoided_traits: list[str]


@dataclass
class EvalConfig:
    ks: tuple[int, ...] = (5, 10, 20)
    book_ids: list[str] | None = None  # None이면 전체 카탈로그, 리스트면 파일럿처럼 후보 제한
    phase: Literal["pilot", "production"] = "pilot"
    seed: int = 42
        # Recall 계산 시 "relevant"로 인정하는 최소 relevance 점수. 원래 기본값 1
    # (relevance>0)로 실험했을 때, relevance 분포가 후한 pilot 데이터에서는 대부분의
    # 책이 relevant로 잡혀 Recall이 무작위 추천과 거의 구분되지 않는 문제가 있었다
    # (실험 근거: ML/eval/analyze_recall_thresholds.py). 팀 논의 후 relevance>=2를
    # 기본값으로 확정 - NDCG는 이 값과 무관하게 항상 0~3 등급을 그대로 가중치로 써서
    # 영향받지 않는다.
    relevant_threshold: int = 2


@dataclass
class UserEvalResult:
    user_id: str
    recall_at_k: dict[int, float]
    ndcg_at_k: dict[int, float | None]
    n_relevant: int


@dataclass
class EvalReport:
    phase: str
    model_name: str
    config: EvalConfig
    metrics: dict[Subset, dict[int, dict[str, float]]]
    per_user: dict[Subset, list[UserEvalResult]]
    generated_at: str


# ── 2. 데이터 로딩 ──────────────────────────────────────────────


def load_interactions(path: str | Path = DEFAULT_INTERACTIONS_PATH) -> list[dict]:
    """user_id, book_id, interaction_type, timestamp 레코드 리스트로 로드."""
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_eval_users(path: str | Path = DEFAULT_EVAL_USERS_PATH) -> dict[str, EvalUser]:
    """user_id -> EvalUser 매핑.

    실제 eval_users.json은 camelCase 필드(userId/preferredEmotions/avoidedTraits)를
    쓰는 레코드 리스트다. userId만 내부 명명 규칙에 맞춰 user_id로 옮겨 담는다.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        item["userId"]: EvalUser(
            user_id=item["userId"],
            preferred_emotions=item.get("preferredEmotions", []),
            avoided_traits=item.get("avoidedTraits", []),
        )
        for item in raw
    }


def load_eval_relevance(
    path: str | Path = DEFAULT_EVAL_RELEVANCE_PATH,
) -> dict[str, dict[str, RelevanceLabel]]:
    """user_id -> {book_id: RelevanceLabel} 중첩 매핑으로 로드.

    실제 eval_relevance.json은 camelCase 필드(userId/isbn/relevance/hasRead/labelSource)를
    쓰는 flat 레코드 리스트다. 책 식별자가 book_id가 아니라 isbn으로 되어 있는데,
    이 프로젝트에서는 isbn을 book_id와 동일한 값 체계로 그대로 사용한다고 가정하고
    로딩 시점에만 isbn -> book_id로 매핑한다(내부 데이터클래스/로직은 전부 book_id로 통일).
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    result: dict[str, dict[str, RelevanceLabel]] = defaultdict(dict)
    for item in raw:
        result[item["userId"]][item["isbn"]] = RelevanceLabel(
            relevance=item.get("relevance"),
            has_read=bool(item.get("hasRead", False)),
            label_source=item.get("labelSource"),
        )
    return dict(result)


# ── 3. 핵심 지표 (유저 1명, k 1개 기준) ───────────────────────────


def recall_at_k(recommended: list[str], relevant_ids: set[str], k: int) -> float:
    """relevance>0인 아이템을 relevant로 간주. |top-k ∩ relevant| / |relevant|."""
    if not relevant_ids:
        raise ValueError("relevant_ids가 비어 있으면 recall을 정의할 수 없습니다.")
    hits = len(set(recommended[:k]) & relevant_ids)
    return hits / len(relevant_ids)


def dcg_at_k(recommended: list[str], relevance_map: dict[str, int], k: int) -> float:
    """graded relevance 기반 DCG@k. relevance_map에 없는(null/미평가) 아이템은 gain=0."""
    dcg = 0.0
    for i, book_id in enumerate(recommended[:k], start=1):
        rel = relevance_map.get(book_id, 0)
        if rel:
            dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def ideal_dcg_at_k(relevance_map: dict[str, int], k: int) -> float:
    """relevance_map 값들을 내림차순 정렬해 만드는 이상적 DCG@k (NDCG 정규화 분모)."""
    sorted_rels = sorted(relevance_map.values(), reverse=True)[:k]
    return sum((2**rel - 1) / math.log2(i + 1) for i, rel in enumerate(sorted_rels, start=1) if rel)


def ndcg_at_k(recommended: list[str], relevance_map: dict[str, int], k: int) -> float | None:
    """dcg_at_k / ideal_dcg_at_k. ideal이 0이면(라벨 전무/전부 0) 집계에서 제외하도록 None 반환."""
    idcg = ideal_dcg_at_k(relevance_map, k)
    if idcg == 0:
        return None
    return dcg_at_k(recommended, relevance_map, k) / idcg


# ── 4. Known/Held-out 분리 (CF 계열 전용, 옵션) ────────────────────


def split_known_held_out(
    eval_relevance: dict[str, dict[str, RelevanceLabel]],
    held_out_ratio: float = 0.3,
    min_relevant_for_split: int = 2,
    seed: int = 42,
) -> tuple[dict[str, set[str]], dict[str, dict[str, RelevanceLabel]]]:
    """유저별 relevance>0 아이템만 known/held_out으로 무작위 분리한다.

    known: 모델 학습/컨텍스트 노출용 book_id 집합 (evaluate_model의 exclude_known 인자로 전달).
    held_out: 정답 비교 전용 서브셋 (evaluate_model의 eval_relevance 인자로 전달).
    relevant 아이템이 min_relevant_for_split 미만인 유저는 분리하지 않고 전부 known으로 남겨
    held_out을 비워, 해당 유저가 평가 대상에서 자동으로 제외되게 한다. relevance가 0이거나
    null인 항목은 애초에 분리 대상이 아니라 held_out에 그대로 남아 "비관련"으로 정상 처리된다.

    ⚠️ 이 함수는 정답 라벨만 분리한다. known 세트로 실제 추천 모델을 (재)학습/워밍업하는 것은
    evaluation.py의 책임 범위 밖이며, 호출부가 이 함수의 반환값을 이용해 별도로 처리해야 한다.
    """
    rng = random.Random(seed)
    known: dict[str, set[str]] = {}
    held_out: dict[str, dict[str, RelevanceLabel]] = {}

    for user_id in sorted(eval_relevance):
        labels = eval_relevance[user_id]
        relevant_ids = sorted(
            bid for bid, lb in labels.items() if lb.relevance is not None and lb.relevance > 0
        )

        if len(relevant_ids) < min_relevant_for_split:
            known[user_id] = set(relevant_ids)
            held_out[user_id] = {}
            continue

        shuffled = relevant_ids[:]
        rng.shuffle(shuffled)
        n_known = max(1, round(len(shuffled) * (1 - held_out_ratio)))
        known_ids = set(shuffled[:n_known])

        known[user_id] = known_ids
        held_out[user_id] = {bid: lb for bid, lb in labels.items() if bid not in known_ids}

    return known, held_out


# ── 5. 평가 오케스트레이션 ──────────────────────────────────────


def _filter_relevance_map(
    relevance_for_user: dict[str, RelevanceLabel],
    has_read_filter: bool | None,
    book_ids: list[str] | None,
) -> dict[str, int]:
    allowed = set(book_ids) if book_ids is not None else None
    return {
        bid: label.relevance
        for bid, label in relevance_for_user.items()
        if label.relevance is not None
        and (allowed is None or bid in allowed)
        and (has_read_filter is None or label.has_read == has_read_filter)
    }


def _evaluate_user_subset(
    user_id: str,
    recommended: list[str],
    relevance_map: dict[str, int],
    ks: tuple[int, ...],
    relevant_threshold: int = 2,
) -> UserEvalResult | None:
    relevant_ids = {bid for bid, rel in relevance_map.items() if rel >= relevant_threshold}
    if not relevant_ids:
        return None
    recall = {k: recall_at_k(recommended, relevant_ids, k) for k in ks}
    ndcg = {k: ndcg_at_k(recommended, relevance_map, k) for k in ks}
    return UserEvalResult(user_id=user_id, recall_at_k=recall, ndcg_at_k=ndcg, n_relevant=len(relevant_ids))


def _aggregate(results: list[UserEvalResult], ks: tuple[int, ...]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = {}
    for k in ks:
        recalls = [r.recall_at_k[k] for r in results]
        ndcgs = [r.ndcg_at_k[k] for r in results if r.ndcg_at_k[k] is not None]
        out[k] = {
            "recall": statistics.fmean(recalls) if recalls else float("nan"),
            "ndcg": statistics.fmean(ndcgs) if ndcgs else float("nan"),
            "n_users": len(recalls),
        }
    return out


def evaluate_model(
    recommend_fn: RecommendFn,
    eval_users: dict[str, EvalUser],
    eval_relevance: dict[str, dict[str, RelevanceLabel]],
    config: EvalConfig,
    model_name: str = "model",
    exclude_known: dict[str, set[str]] | None = None,
) -> EvalReport:
    """recommend_fn을 유저별로 1회(k=max(ks))만 호출해 5/10/20 등 여러 K를 슬라이싱으로 계산한다.

    exclude_known: CF 계열처럼 known/held_out 분리가 필요한 모델은 split_known_held_out()의
    known을 넘기면 추천 리스트에서 해당 book_id를 제거(순위 재정렬 없이 필터링만)한 뒤 채점한다.
    이때 eval_relevance에는 반드시 held_out만 전달해야 한다. 콘텐츠 기반 모델처럼 분리가
    필요 없으면 None(기본값)으로 둔다.
    """
    max_k = max(config.ks)
    subset_results: dict[Subset, list[UserEvalResult]] = {
        "overall": [],
        "has_read_true": [],
        "has_read_false": [],
    }

    for user_id in eval_users:
        relevance_for_user = eval_relevance.get(user_id)
        if not relevance_for_user:
            continue

        recommended = recommend_fn(user_id, max_k)

        if config.book_ids is not None:
            allowed = set(config.book_ids)
            recommended = [b for b in recommended if b in allowed]
        if exclude_known is not None:
            known_ids = exclude_known.get(user_id, set())
            recommended = [b for b in recommended if b not in known_ids]

        for subset, has_read_filter in (
            ("overall", None),
            ("has_read_true", True),
            ("has_read_false", False),
        ):
            relevance_map = _filter_relevance_map(relevance_for_user, has_read_filter, config.book_ids)
            result = _evaluate_user_subset(
                user_id, recommended, relevance_map, config.ks, config.relevant_threshold
            )
            if result is not None:
                subset_results[subset].append(result)

    metrics: dict[Subset, dict[int, dict[str, float]]] = {
        subset: _aggregate(results, config.ks) for subset, results in subset_results.items()
    }

    return EvalReport(
        phase=config.phase,
        model_name=model_name,
        config=config,
        metrics=metrics,
        per_user=subset_results,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _filter_relevance_map_by_label_source(
    relevance_for_user: dict[str, RelevanceLabel],
    label_source_filter: str | None,
    book_ids: list[str] | None,
) -> dict[str, int]:
    allowed = set(book_ids) if book_ids is not None else None
    return {
        bid: label.relevance
        for bid, label in relevance_for_user.items()
        if label.relevance is not None
        and (allowed is None or bid in allowed)
        and (label_source_filter is None or label.label_source == label_source_filter)
    }


def summarize_by_label_source(
    recommend_fn: RecommendFn,
    eval_users: dict[str, EvalUser],
    eval_relevance: dict[str, dict[str, RelevanceLabel]],
    config: EvalConfig,
    label_sources: tuple[str, ...] = ("aspect_card", "read"),
    exclude_known: dict[str, set[str]] | None = None,
) -> dict[str, dict[int, dict[str, float]]]:
    """labelSource("aspect_card"/"read") 기준으로 recall/ndcg를 별도 축으로 집계한다.

    evaluate_model의 hasRead 기반 분리(overall/has_read_true/has_read_false)와는 독립적인
    축이다 — hasRead와 labelSource가 1:1로 대응하지 않기 때문에(예: 안 읽었지만
    aspect_card로 평가한 경우가 기본), 라벨 신뢰도를 다른 관점에서 따로 확인하기 위한 함수다.
    evaluate_model과 별도로 recommend_fn을 다시 호출한다(결과 캐싱/재사용 없음).
    exclude_known 의미는 evaluate_model과 동일하다.
    """
    max_k = max(config.ks)
    per_source_results: dict[str, list[UserEvalResult]] = {source: [] for source in label_sources}

    for user_id in eval_users:
        relevance_for_user = eval_relevance.get(user_id)
        if not relevance_for_user:
            continue

        recommended = recommend_fn(user_id, max_k)

        if config.book_ids is not None:
            allowed = set(config.book_ids)
            recommended = [b for b in recommended if b in allowed]
        if exclude_known is not None:
            known_ids = exclude_known.get(user_id, set())
            recommended = [b for b in recommended if b not in known_ids]

        for source in label_sources:
            relevance_map = _filter_relevance_map_by_label_source(relevance_for_user, source, config.book_ids)
            result = _evaluate_user_subset(
                user_id, recommended, relevance_map, config.ks, config.relevant_threshold
            )
            if result is not None:
                per_source_results[source].append(result)

    return {source: _aggregate(results, config.ks) for source, results in per_source_results.items()}


# ── 6. 리포트 ──────────────────────────────────────────────────

_SUBSET_LABELS: dict[Subset, str] = {
    "overall": "전체",
    "has_read_true": "hasRead=true",
    "has_read_false": "hasRead=false",
}


def print_report(report: EvalReport) -> None:
    print(f"=== 평가 리포트 (phase={report.phase}, model={report.model_name}) ===")
    for subset, label in _SUBSET_LABELS.items():
        print(f"\n[{label}]")
        for k in report.config.ks:
            stats = report.metrics[subset][k]
            print(
                f"  k={k:<3} Recall@{k}={stats['recall']:.4f}  "
                f"NDCG@{k}={stats['ndcg']:.4f}  (n_users={stats['n_users']})"
            )


def save_report(report: EvalReport, path: str | Path | None = None) -> Path:
    """phase 메타데이터를 포함해 JSON으로 저장한다. 나중에 pilot/production 결과를
    나란히 불러와 비교(교차검증)할 수 있도록 phase가 파일명/내용 양쪽에 남는다."""
    if path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = RESULTS_DIR / f"{report.phase}_{report.model_name}_{timestamp}.json"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "phase": report.phase,
        "model_name": report.model_name,
        "config": asdict(report.config),
        "metrics": report.metrics,
        "per_user": {subset: [asdict(r) for r in results] for subset, results in report.per_user.items()},
        "generated_at": report.generated_at,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ── 7. 랜덤 베이스라인 ─────────────────────────────────────────


def random_recommend_fn(book_ids: list[str], seed: int | None = None) -> RecommendFn:
    """매 호출마다 book_ids를 셔플해 상위 k개를 반환하는 RecommendFn. sanity check용 baseline."""
    rng = random.Random(seed)

    def _recommend(user_id: str, k: int = 10) -> list[str]:
        shuffled = book_ids[:]
        rng.shuffle(shuffled)
        return shuffled[:k]

    return _recommend


# ── 8. 이론적 기댓값 (하이퍼기하분포) ───────────────────────────


def expected_recall_at_k_hypergeometric(N: int, k_relevant: int, k: int) -> float:
    """유저 1명 기준 Recall@k 이론적 기댓값.

    무작위로 섞은 N개 중 k개를 뽑을 때 relevant(k_relevant개) 히트 수는
    Hypergeometric(N, k_relevant, k)를 따르고 E[hits] = k*k_relevant/N.
    Recall@k = hits/k_relevant이므로 E[Recall@k] = k/N이 되어 k_relevant 값 자체와는
    무관해진다(하이퍼기하분포 평균의 선형성에 따른 결과, 버그 아님).
    """
    if N <= 0:
        raise ValueError("N은 1 이상이어야 합니다.")
    if k_relevant <= 0:
        raise ValueError("k_relevant가 0이면 Recall이 정의되지 않습니다.")
    if k_relevant > N:
        raise ValueError("k_relevant는 N을 넘을 수 없습니다.")

    k_eff = min(k, N)
    expected_hits = k_eff * k_relevant / N
    return expected_hits / k_relevant


def expected_recall_at_k_for_users(
    N: int, k_relevant_per_user: list[int], k: int
) -> tuple[list[float], float]:
    """유저별 Recall@k 이론적 기댓값 리스트와 전체 평균을 함께 반환. relevant 0인 유저는 제외."""
    per_user = [expected_recall_at_k_hypergeometric(N, kr, k) for kr in k_relevant_per_user if kr > 0]
    if not per_user:
        raise ValueError("relevant 아이템이 1개 이상인 유저가 없습니다.")
    return per_user, statistics.fmean(per_user)


def simulate_random_ndcg_at_k(
    N: int,
    relevance_by_book_per_user: list[dict[str, int]],
    k: int,
    n_trials: int = 10000,
    seed: int = 42,
) -> float:
    """[근사치] 무작위 추천의 NDCG@k 기댓값은 알려진 폐형식이 없어 몬테카를로로 근사한다.

    유저별 relevance_map(라벨 있는 book_id만) 외 나머지 N-len(book_ids)개는 관련도 0인
    "filler"로 채운 전체 후보 풀을 n_trials회 무작위로 섞어 ndcg_at_k를 계산한 뒤 평균낸다.
    n_trials가 클수록 근사 정확도가 오르고 표준오차는 1/sqrt(n_trials)로 감소한다.
    """
    rng = random.Random(seed)
    per_user_means = []

    for relevance_map in relevance_by_book_per_user:
        if not relevance_map or all(rel == 0 for rel in relevance_map.values()):
            continue

        book_ids = list(relevance_map.keys())
        filler_count = max(N - len(book_ids), 0)
        pool = book_ids + [f"__filler_{i}__" for i in range(filler_count)]

        scores = []
        for _ in range(n_trials):
            rng.shuffle(pool)
            scores.append(ndcg_at_k(pool, relevance_map, k) or 0.0)
        per_user_means.append(statistics.fmean(scores))

    if not per_user_means:
        raise ValueError("유효한 relevance_map이 없습니다 (전부 비어있거나 relevance가 모두 0).")
    return statistics.fmean(per_user_means)


# ── 9. 이론 vs 실측 비교 ────────────────────────────────────────


def compare_theoretical_vs_empirical(
    theoretical: dict[int, float],
    empirical: dict[int, float],
    empirical_std_err: dict[int, float] | None = None,
    n_sigma: float = 3.0,
    abs_tolerance: float = 0.02,
) -> dict[int, dict[str, float | bool]]:
    """k별로 이론값과 실측값 차이를 오차 허용범위와 비교한다.

    empirical_std_err가 주어지면 n_sigma * std_err를 허용범위로 쓰고, 없으면 abs_tolerance를
    폴백으로 쓴다. 허용범위를 벗어나면 해당 k에 대해 콘솔에 "버그 의심" 경고를 출력한다.
    """
    result: dict[int, dict[str, float | bool]] = {}
    for k in theoretical:
        if k not in empirical:
            continue
        diff = abs(theoretical[k] - empirical[k])
        if empirical_std_err and k in empirical_std_err and empirical_std_err[k] > 0:
            tolerance = n_sigma * empirical_std_err[k]
        else:
            tolerance = abs_tolerance
        within_tolerance = diff <= tolerance

        result[k] = {
            "theoretical": theoretical[k],
            "empirical": empirical[k],
            "diff": diff,
            "tolerance": tolerance,
            "within_tolerance": within_tolerance,
        }
        if not within_tolerance:
            print(
                f"[경고] k={k}: 이론값({theoretical[k]:.4f})과 실측값({empirical[k]:.4f})의 "
                f"차이({diff:.4f})가 허용오차(±{tolerance:.4f})를 초과함 — 평가 코드 버그 의심"
            )
    return result


if __name__ == "__main__":
    # 실제 eval_data 파일이 아직 없어, 동작 확인용 synthetic 데이터로 self-check를 수행한다.
    book_ids = [f"b{i:03d}" for i in range(1, 21)]  # N=20권 가상 카탈로그

    synthetic_users = {
        "u001": EvalUser("u001", ["잔잔함", "위로"], ["신파"]),
        "u002": EvalUser("u002", ["설렘"], []),
        "u003": EvalUser("u003", ["그리움"], ["잔인한 묘사"]),
    }

    synthetic_relevance: dict[str, dict[str, RelevanceLabel]] = {
        "u001": {
            "b001": RelevanceLabel(relevance=3, has_read=True, label_source="read"),
            "b002": RelevanceLabel(relevance=2, has_read=True, label_source="read"),
            "b005": RelevanceLabel(relevance=1, has_read=False, label_source="aspect_card"),
            "b010": RelevanceLabel(relevance=0, has_read=False, label_source="aspect_card"),
        },
        "u002": {
            "b003": RelevanceLabel(relevance=3, has_read=False, label_source="aspect_card"),
            "b004": RelevanceLabel(relevance=2, has_read=False, label_source="aspect_card"),
        },
        "u003": {
            "b006": RelevanceLabel(relevance=3, has_read=True, label_source="read"),
            "b007": RelevanceLabel(relevance=1, has_read=True, label_source="aspect_card"),
            "b008": RelevanceLabel(relevance=None, has_read=False, label_source="aspect_card"),
        },
    }

    config = EvalConfig(ks=(5, 10, 20), phase="pilot", seed=42)

    print(">>> 1. 콘텐츠 기반(스플릿 없음) 랜덤 베이스라인 평가")
    baseline_fn = random_recommend_fn(book_ids, seed=config.seed)
    report = evaluate_model(
        baseline_fn, synthetic_users, synthetic_relevance, config, model_name="random_baseline"
    )
    print_report(report)
    saved_path = save_report(report)
    print(f"\n저장 완료: {saved_path}")

    print("\n>>> 2. Known/Held-out 분리 예시 (CF 계열 가정)")
    known, held_out = split_known_held_out(
        synthetic_relevance, held_out_ratio=0.5, min_relevant_for_split=2, seed=config.seed
    )
    split_report = evaluate_model(
        baseline_fn,
        synthetic_users,
        held_out,
        config,
        model_name="random_baseline_split",
        exclude_known=known,
    )
    print_report(split_report)

    print("\n>>> 3. 하이퍼기하분포 이론값 vs 실측값 비교 (Random Baseline sanity check)")
    N = len(book_ids)
    k_relevant_per_user = [
        len(
            [
                r
                for r in labels.values()
                if r.relevance is not None and r.relevance >= config.relevant_threshold
            ]
        )
        for labels in synthetic_relevance.values()
    ]
    theoretical_recall = {}
    for k in config.ks:
        _, mean_expected = expected_recall_at_k_for_users(N, k_relevant_per_user, k)
        theoretical_recall[k] = mean_expected

    empirical_recall = {k: report.metrics["overall"][k]["recall"] for k in config.ks}

    empirical_std_err = {}
    for k in config.ks:
        recalls = [r.recall_at_k[k] for r in report.per_user["overall"]]
        empirical_std_err[k] = statistics.stdev(recalls) / math.sqrt(len(recalls)) if len(recalls) > 1 else 0.0

    compare_theoretical_vs_empirical(theoretical_recall, empirical_recall, empirical_std_err)
    for k in config.ks:
        print(
            f"  k={k}: 이론={theoretical_recall[k]:.4f}  실측={empirical_recall[k]:.4f}  "
            f"(표준오차={empirical_std_err[k]:.4f})"
        )

    print("\n>>> 4. NDCG 몬테카를로 근사 기댓값 (참고용, 소규모 n_trials)")
    ndcg_relevance_maps = [
        {bid: lb.relevance for bid, lb in labels.items() if lb.relevance is not None}
        for labels in synthetic_relevance.values()
    ]
    approx_ndcg_at_5 = simulate_random_ndcg_at_k(N, ndcg_relevance_maps, k=5, n_trials=500, seed=config.seed)
    print(f"  E[NDCG@5] (근사, n_trials=500) = {approx_ndcg_at_5:.4f}")

    print("\n>>> 5. labelSource(aspect_card/read) 기준 별도 축 집계")
    by_source = summarize_by_label_source(baseline_fn, synthetic_users, synthetic_relevance, config)
    for source, per_k in by_source.items():
        print(f"  [{source}]")
        for k in config.ks:
            stats = per_k[k]
            print(
                f"    k={k:<3} Recall@{k}={stats['recall']:.4f}  "
                f"NDCG@{k}={stats['ndcg']:.4f}  (n_users={stats['n_users']})"
            )