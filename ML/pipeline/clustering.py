"""Phase 2 — 전체 리뷰를 한 번에 KMeans로 클러스터링해 "결"을 전 책 공통으로
정의하고, 책 단위로는 그 결들에 대한 (centroid, weight) 분포만 집계한다.

DESIGN.md 5.Phase 2 참고:
- 입력: 전체 책의 모든 리뷰 임베딩 (하나의 pool, 책 구분 없이 한 번에 클러스터링)
- 방법: KMeans 1회 수행 -> 리뷰마다 전역 클러스터 ID 하나 (노이즈 개념 없음)
- 책 단위 후처리 (평균으로 합치지 않음 - 방식 1):
    weight = 그 클러스터에 속한 이 책 리뷰 수 / 이 책 전체 리뷰 수
    책의 아이덴티티 = (전역 centroid, weight) 쌍의 리스트 그 자체
- weight는 벡터를 섞는 데 쓰지 않는다. 대표 결 선정(Phase 2.5/5)이나 신뢰도 낮은
  결을 걸러내는 임계값 정도로만 쓰이고, 매칭(Phase 4)은 벡터별 유사도의 최댓값을 쓴다.

## HDBSCAN 대신 KMeans를 쓰는 이유 (팀 확정, experiment_hdbscan_vs_kmeans.py 참고)

실 데이터(440개 리뷰, 88권)에 HDBSCAN을 돌려보면 파라미터를 어떻게 조합해도
"리뷰의 90%가 노이즈로 버려짐" 아니면 "리뷰 대부분이 거대 클러스터 하나로 뭉침"
두 실패 패턴만 반복됐다 - 이 규모의 자연어 리뷰 임베딩 공간이 밀도 기반
클러스터링이 기대하는 뚜렷한 밀집/공백 경계 없이 완만하게 이어져 있기 때문으로
보인다. 같은 임베딩에 KMeans(고정 k)를 쓰면 클러스터 크기가 고르게 분포하고,
클러스터마다 다수의 책에 걸쳐 있으며, 클러스터별 호/불호 비율도 뚜렷이 갈리는
훨씬 유의미한 구조가 나왔다. DEFAULT_N_CLUSTERS=30은 이 실험에서 확인된 값이다.

## "캐치올 클러스터" 제외 (DEFAULT_COVERAGE_THRESHOLD)

책이 걸쳐 있는 어떤 결이 전체 책의 상당수(예: 80%+)를 커버하면, 그 결에서는
책들이 전부 "같은 전역 centroid"를 공유하게 되어 max-similarity 매칭 시 다수의
책이 동점(구조적으로는 최댓값이 완전히 같아지는 것도 가능)을 받는다 - 방식1이
지키려는 "결을 보존해서 세밀하게 매칭"이라는 목표가 무력화되는 역설이다.
실제로 k=30일 때 무작위 유저 벡터로 최악의 경우를 실험하면 책 88권 중 다수가
동점 처리됐다. 그래서 "전체 책 중 coverage_threshold 이상을 커버하는 클러스터"는
너무 일반적이라 변별력이 없다고 보고 매칭 후보에서 제외한다. threshold=0.3
(30%)일 때 orphaned(결이 하나도 안 남는 책)=0, 최악의 경우 동점 수가 그리드
서치 전체에서 최소였다 (자세한 수치는 experiment_hdbscan_vs_kmeans.py 참고).
단, 한 책의 모든 결이 이 제외 대상이 되면(즉 그 책의 유일한 결이 캐치올뿐이면)
그 책이 아예 결 없는 상태가 되어버리므로, 이 경우에는 예외적으로 제외를
적용하지 않고 원래 결을 그대로 쓴다 (orphaned 방지, compute_book_identities 참고).

## "결이 많은 책"이 구조적으로 유리해지는 문제와 max_facets

Phase 4의 max-similarity는 "여러 후보 중 가장 잘 맞는 것 하나"를 뽑기 때문에,
후보(결) 개수가 많은 책일수록 유저 취향과 무관하게 그냥 우연히 더 높은 점수가
나올 확률이 커진다 (순서통계량 문제). 실제 데이터(k=30 KMeans)로 검증한 결과,
취향과 전혀 무관한 무작위 유저 벡터 200개에 대해서도 "책의 결 개수"와 "평균
max-similarity 점수" 사이에 상관계수 0.70이 나왔다 - 진짜 취향 매칭과 무관한
구조적 편향임을 확인. 책마다 남기는 결의 개수를 weight 기준 상위 N개로 캡(cap)
해서 같은 실험을 반복하면:
  cap=1 -> 상관계수 -0.25 (편향은 없어지지만 사실상 방식2처럼 벡터 1개로
           축소되어 "여러 결 보존"이라는 목적 자체가 무너짐)
  cap=2 -> 상관계수  0.05 (편향이 거의 사라지면서 결을 2개까지는 보존)
  cap=3 -> 상관계수  0.34 (편향이 아직 눈에 띄게 남음)
  cap 없음 -> 상관계수 0.70
따라서 DEFAULT_MAX_FACETS=2를 기본값으로 둔다.

metric: embedding.py의 embed()가 normalize_embeddings=True로 L2 정규화된 벡터를
생성하므로, KMeans의 유클리드 거리 기반 군집화가 코사인 유사도 기준과 사실상
동일하게 작동한다 (정규화된 벡터에서는 두 거리의 순위가 같다).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

DEFAULT_N_CLUSTERS = 30
DEFAULT_RANDOM_STATE = 42
DEFAULT_MAX_FACETS = 2
DEFAULT_COVERAGE_THRESHOLD = 0.3


@dataclass
class GlobalClusterResult:
    review_ids: list[str]
    book_ids: list[str]
    labels: np.ndarray  # 리뷰별 전역 클러스터 라벨 (KMeans는 노이즈 개념이 없음)
    centroids: dict[int, np.ndarray]  # {전역 cluster_label: centroid_vector}


@dataclass
class BookIdentity:
    book_id: str
    cluster_vectors: dict[int, np.ndarray] = field(default_factory=dict)  # {전역 cluster_label: centroid}
    cluster_weights: dict[int, float] = field(default_factory=dict)  # {전역 cluster_label: weight}

    def vectors(self) -> list[np.ndarray]:
        """이 책의 '결' 벡터들 (평균 내지 않고 그대로 여러 개). Phase 4 max-similarity 입력."""
        return list(self.cluster_vectors.values())


def global_cluster(
    review_ids: list[str],
    book_ids: list[str],
    embeddings: np.ndarray,
    n_clusters: int = DEFAULT_N_CLUSTERS,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> GlobalClusterResult:
    """책 구분 없이 전체 리뷰 임베딩을 KMeans로 한 번에 클러스터링한다.

    책 간에 "결"의 기준을 공유하기 위한 단계이므로, 여기서 book_ids는 결과를 각
    책으로 다시 나눠 돌려주기 위한 딱지일 뿐, 클러스터링 자체에는 관여하지 않는다.
    """
    effective_k = min(n_clusters, len(embeddings))
    km = KMeans(n_clusters=effective_k, n_init=10, random_state=random_state).fit(embeddings)
    labels = km.labels_
    centroids = {label: km.cluster_centers_[label] for label in range(effective_k)}

    return GlobalClusterResult(
        review_ids=review_ids, book_ids=book_ids, labels=labels, centroids=centroids
    )


def compute_cluster_coverage(result: GlobalClusterResult) -> dict[int, float]:
    """전역 클러스터별로 전체 책 중 몇 %가 이 클러스터에 리뷰를 갖고 있는지 계산한다."""
    total_books = len(set(result.book_ids))
    books_per_label: dict[int, set[str]] = {}
    for book_id, label in zip(result.book_ids, result.labels):
        books_per_label.setdefault(label, set()).add(book_id)
    return {label: len(books) / total_books for label, books in books_per_label.items()}


def compute_book_identities(
    result: GlobalClusterResult,
    min_weight: float = 0.0,
    max_facets: int | None = DEFAULT_MAX_FACETS,
    coverage_threshold: float | None = DEFAULT_COVERAGE_THRESHOLD,
) -> dict[str, BookIdentity]:
    """전역 클러스터링 결과를 책 단위로 집계한다 (평균 없이 (centroid, weight) 리스트).

    min_weight: 이 값 미만인 weight를 가진 결은 신뢰도가 낮다고 보고 걸러낸다.
    기본값 0.0(필터링 없음).

    coverage_threshold: 전체 책 중 이 비율 이상을 커버하는 "캐치올" 클러스터는
    변별력이 없다고 보고 매칭 후보에서 제외한다 (자세한 근거는 모듈 docstring
    참고). None이면 제외하지 않는다. 이 제외로 인해 한 책의 결이 전부 사라지면
    그 책에 한해서는 예외적으로 제외를 적용하지 않는다(orphaned 방지).

    max_facets: 책마다 남기는 결의 최대 개수. weight가 높은 순으로 상위 max_facets개만
    남기고 나머지는 버린다. "결이 많은 책일수록 max-similarity 매칭에서 구조적으로
    유리해지는" 문제를 완화하기 위함 (자세한 근거는 모듈 docstring 참고). None이면
    제한 없음.
    """
    review_counts: Counter[str] = Counter(result.book_ids)
    label_counts: dict[str, Counter[int]] = {}
    for book_id, label in zip(result.book_ids, result.labels):
        label_counts.setdefault(book_id, Counter())[label] += 1

    excluded_labels: set[int] = set()
    if coverage_threshold is not None:
        coverage = compute_cluster_coverage(result)
        excluded_labels = {label for label, cov in coverage.items() if cov > coverage_threshold}

    identities: dict[str, BookIdentity] = {}
    for book_id in sorted(review_counts):
        identity = BookIdentity(book_id=book_id)
        total = review_counts[book_id]
        raw_weights = {
            label: count / total
            for label, count in label_counts.get(book_id, Counter()).items()
            if count / total >= min_weight
        }
        weights = {label: w for label, w in raw_weights.items() if label not in excluded_labels}
        if not weights and raw_weights:
            weights = raw_weights  # 전부 캐치올로 제외되면 orphaned 방지를 위해 원래 결을 그대로 씀

        kept_labels = sorted(weights, key=weights.get, reverse=True)
        if max_facets is not None:
            kept_labels = kept_labels[:max_facets]

        for label in kept_labels:
            identity.cluster_vectors[label] = result.centroids[label]
            identity.cluster_weights[label] = weights[label]
        identities[book_id] = identity

    return identities


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from embedding import load_embeddings

    embeddings_path = Path(__file__).parent / "mock_data" / "embeddings.npz"
    book_ids, review_ids, sentences, embeddings = load_embeddings(embeddings_path)

    reviews_path = Path(__file__).parent / "mock_data" / "reviews.json"
    with open(reviews_path, encoding="utf-8") as f:
        data = json.load(f)
    mock_label_map = {r["review_id"]: r["meta"]["label"] for r in data["reviews"]}
    title_map = {b["book_id"]: b["title"] for b in data["books"]}

    # 주의: 기본값 n_clusters=30은 실 데이터(440개 리뷰) 규모를 가정한 값이다.
    # 이 mock 데이터는 45개 리뷰(5권)뿐이라 그대로 쓰면 클러스터당 평균 1.5개
    # 리뷰밖에 안 남아 의미가 없으므로, 데모에서는 더 작은 값을 쓴다.
    demo_n_clusters = 6
    result = global_cluster(review_ids, book_ids, embeddings, n_clusters=demo_n_clusters)
    identities = compute_book_identities(result)

    print(f"[데모 파라미터: n_clusters={demo_n_clusters} (기본값 30은 440개 실 데이터 규모용)]")
    print(f"전체 리뷰 {len(review_ids)}개 -> 전역 클러스터 {len(result.centroids)}개\n")

    by_book: dict[str, list[tuple[str, int]]] = {}
    for rid, bid, label in zip(result.review_ids, result.book_ids, result.labels):
        by_book.setdefault(bid, []).append((rid, label))

    for book_id in sorted(by_book):
        print(f"=== {book_id} {title_map[book_id]} ===")
        for rid, label in by_book[book_id]:
            print(f"  {rid} ({mock_label_map[rid]:>2}) -> 전역 cluster {label}")
        identity = identities[book_id]
        print(f"  이 책이 걸쳐 있는 결(전역 클러스터) 수: {len(identity.cluster_vectors)}")
        for label, weight in sorted(identity.cluster_weights.items(), key=lambda x: -x[1]):
            print(f"    cluster {label}: weight={weight:.2f}")
        print()
