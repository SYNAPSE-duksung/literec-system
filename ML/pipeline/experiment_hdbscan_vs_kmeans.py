"""[실험용 스크립트 - 아직 파이프라인에 반영되지 않음]

Phase 2 글로벌 클러스터링 방법을 HDBSCAN(DESIGN.md에 명시된 현재 방법) vs
KMeans(고정 k)로 비교하기 위한 실험이다. 팀원과 상의해서 방법을 확정하기 전까지는
clustering.py나 DESIGN.md를 수정하지 않고, 이 스크립트로만 결과를 재현/공유한다.

배경: 실제 440개 리뷰(88권)를 embedding.py로 임베딩한 뒤 DESIGN.md대로 HDBSCAN을
돌려보니, min_cluster_size/min_samples를 어떻게 조합해도 다음 두 실패 패턴만
반복됐다:
  1. 엄격한 파라미터(팀원 제안값 min_cluster_size=5, min_samples=3) -> 리뷰의
     90%가 노이즈(-1)로 버려지고 클러스터 2개만 발견
  2. 완화한 파라미터 -> 리뷰 대부분(440개 중 361개)이 호/불호/혼재 비율이 원본과
     거의 같은 거대한 클러스터 하나로 뭉쳐버림 (== "결"을 구분한 게 아니라 그냥
     전체를 한 덩어리로 묶은 것과 다름없음)
  이 패턴은 5축을 합친 문장이든, 소재_및_주제를 뺀 문장이든, 축 하나만 따로
  뽑아도(예: 좋았던_요소만) 똑같이 나타났다. 즉 축 구성 문제가 아니라, 이 정도
  규모(440개)의 자연어 리뷰 임베딩 공간 자체가 HDBSCAN이 기대하는 "밀집 지역 vs
  빈 공간"의 뚜렷한 경계 없이 완만하게 이어져 있어서 밀도 기반 클러스터링이
  구조를 못 찾는 것으로 보인다.

반면 KMeans(고정 k)로 같은 임베딩을 돌리면 클러스터 크기가 고르게 분포하고,
클러스터마다 다수의 책에 걸쳐 있으며, 클러스터별 호/불호 비율도 뚜렷하게
갈린다 (아래 실행 결과 참고). 이 스크립트는 그 비교를 재현한다.

추가 검증(캐치올 클러스터 문제): KMeans로 넘어가도 남는 문제가 하나 있다.
클러스터 하나가 책의 80%+ 를 커버하는 경우, 그 결에서는 책들이 전부 "같은
전역 centroid"를 공유하게 되어 max-similarity 매칭 시 유저 벡터가 그 결과
가까울수록 다수의 책이 동점(극단적으로는 정확히 1.0)을 받는다 — 방식1이
지키려던 "결을 보존해서 세밀하게 매칭"이라는 목표가 무력화되는 역설이다.
아래 두 가지를 조합해서 완화를 시도했다:
  1) k를 늘려서 애초에 결을 더 잘게 쪼갬
  2) 책 커버리지가 임계값(threshold)을 넘는 클러스터는 "너무 일반적이라
     변별력이 없다"고 보고 매칭 후보에서 제외

grid search 결과(k=[10,15,20,30,40,50] x threshold=[0.3,0.4,0.5]):
  - k>=20부터는 "필터링 후 결이 하나도 안 남는 책"(orphaned)이 0건으로
    해결된다.
  - 하지만 "최악의 경우 동점 수"는 k를 30/40/50으로 올려도 24~33권 선에서
    더 줄지 않고 정체된다. 즉 데이터 안에 "책마다 달라지지 않는 일반적인
    감상 표현"이 전체의 약 30% 정도 실재해서, 아무리 잘게 쪼개도 그 덩어리
    자체는 사라지지 않는 것으로 보인다.
  - 결론: 이 조합은 73권 동점 -> 24~33권 동점으로 확실히 개선되지만,
    완전한 해결책은 아니다. (권장 조합으로 k=30, threshold=0.3 정도를
    제시하되, 남은 동점 문제는 팀 논의가 더 필요함을 그대로 공유한다)

사용법(ML 폴더에서):
  uv run python pipeline/experiment_hdbscan_vs_kmeans.py
  (pipeline/real_embeddings.npz가 없으면 자동으로 생성한다 - 최초 실행 시
  ko-sroberta-multitask 모델 다운로드 및 임베딩 계산으로 몇 분 걸릴 수 있음)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN, KMeans

import sys

sys.path.insert(0, str(Path(__file__).parent))
from embedding import embed_reviews, load_embeddings, save_embeddings

STRUCTURED_REVIEWS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "processed" / "structured_reviews.jsonl"
)
REAL_EMBEDDINGS_PATH = Path(__file__).parent / "real_embeddings.npz"

HDBSCAN_PARAM_GRID = [(5, 3), (5, 2), (4, 2), (3, 2), (3, 1)]
KMEANS_K_GRID = [5, 8, 10, 15, 20]


def load_or_build_embeddings() -> tuple[list[str], list[str], list[str], np.ndarray]:
    if REAL_EMBEDDINGS_PATH.exists():
        return load_embeddings(REAL_EMBEDDINGS_PATH)

    reviews = []
    with open(STRUCTURED_REVIEWS_PATH, encoding="utf-8") as f:
        for line in f:
            reviews.append(json.loads(line))

    sentences, embeddings = embed_reviews(reviews)
    book_ids = [r["book_id"] for r in reviews]
    review_ids = [r["review_id"] for r in reviews]
    save_embeddings(REAL_EMBEDDINGS_PATH, book_ids, review_ids, sentences, embeddings)
    return book_ids, review_ids, sentences, embeddings


def load_label_map() -> dict[str, str]:
    label_map = {}
    with open(STRUCTURED_REVIEWS_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            label_map[r["review_id"]] = r["meta"]["label"]
    return label_map


def run_hdbscan_sweep(
    book_ids: list[str], review_ids: list[str], embeddings: np.ndarray
) -> None:
    print("=" * 70)
    print("[HDBSCAN] DESIGN.md에 명시된 현재 방법 (파라미터 그리드)")
    print("=" * 70)
    for mcs, ms in HDBSCAN_PARAM_GRID:
        clusterer = HDBSCAN(min_cluster_size=mcs, min_samples=ms, metric="euclidean")
        labels = clusterer.fit_predict(embeddings)
        noise = int(np.sum(labels == -1))
        sizes = Counter(l for l in labels if l != -1)
        top_sizes = sorted(sizes.values(), reverse=True)[:6]
        biggest = max(sizes, key=sizes.get) if sizes else None
        books_biggest = (
            len({b for b, l in zip(book_ids, labels) if l == biggest})
            if biggest is not None
            else None
        )
        print(
            f"  min_cluster_size={mcs} min_samples={ms} -> "
            f"클러스터={len(sizes)}개, 노이즈={noise}/{len(labels)}, "
            f"상위 크기={top_sizes}, 최대 클러스터가 걸친 책 수={books_biggest}"
        )


def run_kmeans_sweep(
    book_ids: list[str],
    review_ids: list[str],
    embeddings: np.ndarray,
    label_map: dict[str, str],
) -> None:
    print()
    print("=" * 70)
    print("[KMeans] 고정 k 파티셔닝 (대안 제안)")
    print("=" * 70)
    for k in KMEANS_K_GRID:
        km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(embeddings)
        labels = km.labels_
        sizes = Counter(labels)
        books_span = sorted(
            (len({b for b, l in zip(book_ids, labels) if l == c}) for c in range(k)),
            reverse=True,
        )
        print(
            f"  k={k} -> 클러스터 크기={sorted(sizes.values(), reverse=True)}, "
            f"클러스터별 걸친 책 수={books_span}"
        )

    print()
    print(f"[KMeans k=10 상세 - 클러스터별 호/불호/혼재 분포 및 대표 문장]")
    k = 10
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(embeddings)
    labels = km.labels_
    _, _, sentences, _ = load_or_build_embeddings()
    for c in range(k):
        idxs = [i for i, l in enumerate(labels) if l == c]
        ld = Counter(label_map[review_ids[i]] for i in idxs)
        print(f"  --- cluster {c} (n={len(idxs)}) label_dist={dict(ld)} ---")
        for i in idxs[:2]:
            print(f"      {sentences[i][:100]}")


def _fit_normalized_kmeans(embeddings: np.ndarray, k: int, seed: int = 42):
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(embeddings)
    centroids = km.cluster_centers_
    centroids = centroids / np.linalg.norm(centroids, axis=1, keepdims=True)
    return km.labels_, centroids


def _book_cluster_sets(book_ids: list[str], labels: np.ndarray) -> dict[str, set[int]]:
    book_clusters: dict[str, set[int]] = {}
    for b, l in zip(book_ids, labels):
        book_clusters.setdefault(b, set()).add(int(l))
    return book_clusters


def analyze_kmeans_plus_exclusion(
    book_ids: list[str],
    embeddings: np.ndarray,
    k: int,
    coverage_threshold: float,
) -> dict:
    """옵션1(k 키우기) + 옵션3(넓은 클러스터 매칭 제외) 조합을 평가한다.

    - orphaned: 필터링 후 매칭에 쓸 결이 하나도 안 남는 책의 수 (0이어야 안전)
    - tie: 최악의 경우(유저 벡터가 남은 것 중 가장 넓은 클러스터와 정확히
      일치) 1위와 동점인 책의 수 - 작을수록 변별력이 좋다는 뜻
    """
    n_books = len(set(book_ids))
    labels, centroids = _fit_normalized_kmeans(embeddings, k)
    book_clusters = _book_cluster_sets(book_ids, labels)

    coverage = {
        c: len({b for b, l in zip(book_ids, labels) if l == c}) / n_books
        for c in range(k)
    }
    excluded = {c for c, v in coverage.items() if v > coverage_threshold}
    remaining = k - len(excluded)

    orphaned = sum(1 for cs in book_clusters.values() if not (cs - excluded))

    remaining_cov = {c: v for c, v in coverage.items() if c not in excluded}
    if not remaining_cov:
        return dict(k=k, threshold=coverage_threshold, remaining=remaining, orphaned=orphaned, tie=None)

    worst_cluster = max(remaining_cov, key=remaining_cov.get)
    user_vec = centroids[worst_cluster]

    def max_sim(cluster_set: set[int]) -> float:
        candidates = cluster_set - excluded
        if not candidates:
            candidates = cluster_set  # 전부 걸러지면 원래 결로 폴백 (orphaned 방지)
        return max(float(np.dot(user_vec, centroids[c])) for c in candidates)

    scores = sorted((max_sim(cs) for cs in book_clusters.values()), reverse=True)
    tie = sum(1 for s in scores if abs(s - scores[0]) < 1e-6)

    return dict(
        k=k,
        threshold=coverage_threshold,
        remaining=remaining,
        orphaned=orphaned,
        max_remaining_coverage=round(max(remaining_cov.values()), 2),
        tie=tie,
    )


def run_kmeans_plus_exclusion_sweep(book_ids: list[str], embeddings: np.ndarray) -> None:
    print()
    print("=" * 70)
    print('[옵션1 + 옵션3 조합] k 확대 + 캐치올 클러스터(책 커버리지 초과) 매칭 제외')
    print("=" * 70)
    print(f"{'k':>4} {'threshold':>10} {'remaining':>10} {'orphaned':>9} {'max_cov':>8} {'worst_tie':>10}")
    for k in [10, 15, 20, 30, 40, 50]:
        for threshold in [0.3, 0.4, 0.5]:
            r = analyze_kmeans_plus_exclusion(book_ids, embeddings, k, threshold)
            print(
                f"{r['k']:>4} {r['threshold']:>10} {r['remaining']:>10} "
                f"{r['orphaned']:>9} {r.get('max_remaining_coverage', '-'):>8} {r['tie']:>10}"
            )

    print()
    print("[권장 조합] k=30, threshold=0.3 상세:")
    r = analyze_kmeans_plus_exclusion(book_ids, embeddings, k=30, coverage_threshold=0.3)
    print(f"  {r}")
    print(
        "  -> orphaned=0(모든 책이 매칭 가능한 결을 최소 1개 유지)이지만, "
        "worst_tie는 여전히 20권대 - 완전 해결은 아님. 팀 논의 필요."
    )


if __name__ == "__main__":
    book_ids, review_ids, sentences, embeddings = load_or_build_embeddings()
    label_map = load_label_map()
    print(f"전체 리뷰 {len(review_ids)}개, 책 {len(set(book_ids))}권\n")

    run_hdbscan_sweep(book_ids, review_ids, embeddings)
    run_kmeans_sweep(book_ids, review_ids, embeddings, label_map)
    run_kmeans_plus_exclusion_sweep(book_ids, embeddings)
