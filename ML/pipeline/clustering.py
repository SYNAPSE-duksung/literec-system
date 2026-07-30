"""Phase 2 — 전체 리뷰를 한 번에 HDBSCAN으로 클러스터링해 "결"을 전 책 공통으로
정의하고, 책 단위로는 그 결들에 대한 (centroid, weight) 분포만 집계한다.

DESIGN.md 5.Phase 2 참고:
- 입력: 전체 책의 모든 리뷰 임베딩 (하나의 pool, 책 구분 없이 한 번에 클러스터링)
- 방법: HDBSCAN 1회 수행 -> 리뷰마다 전역 클러스터 ID(또는 노이즈 -1) 하나
- 책 단위 후처리 (평균으로 합치지 않음 - 방식 1):
    weight = 그 클러스터에 속한 이 책 리뷰 수 / 이 책 전체 리뷰 수
    책의 아이덴티티 = (전역 centroid, weight) 쌍의 리스트 그 자체
- weight는 벡터를 섞는 데 쓰지 않는다. 대표 결 선정(Phase 2.5/5)이나 신뢰도 낮은
  결을 걸러내는 임계값 정도로만 쓰이고, 매칭(Phase 4)은 벡터별 유사도의 최댓값을 쓴다.

"결이 많은 책"이 구조적으로 유리해지는 문제와 max_facets: Phase 4의 max-similarity는
"여러 후보 중 가장 잘 맞는 것 하나"를 뽑기 때문에, 후보(결) 개수가 많은 책일수록
유저 취향과 무관하게 그냥 우연히 더 높은 점수가 나올 확률이 커진다 (순서통계량
문제). 실제 데이터(k=30 KMeans, 실제 리뷰 440개 기준)로 검증한 결과, 취향과 전혀
무관한 무작위 유저 벡터 200개에 대해서도 "책의 결 개수"와 "평균 max-similarity
점수" 사이에 상관계수 0.70이 나왔다 - 진짜 취향 매칭과 무관한 구조적 편향임을
확인. 책마다 남기는 결의 개수를 weight 기준 상위 N개로 캡(cap)해서 같은 실험을
반복하면:
  cap=1 -> 상관계수 -0.25 (편향은 없어지지만 사실상 방식2처럼 벡터 1개로
           축소되어 "여러 결 보존"이라는 목적 자체가 무너짐)
  cap=2 -> 상관계수  0.05 (편향이 거의 사라지면서 결을 2개까지는 보존)
  cap=3 -> 상관계수  0.34 (편향이 아직 눈에 띄게 남음)
  cap 없음(최대 5개) -> 상관계수 0.70
따라서 DEFAULT_MAX_FACETS=2를 기본값으로 둔다 (weight 상위 2개만 남기고 나머지는
버림). compute_book_identities()의 max_facets 인자로 조정 가능.

DEFAULT_MIN_CLUSTER_SIZE=5, DEFAULT_MIN_SAMPLES=3은 팀원이 제안한 시작값이며 아직
확정이 아니다 (DESIGN.md 7절). 기존 책 단위 실험에서 얻은 min_cluster_size=3,
min_samples=2는 책 하나(9개 남짓)를 대상으로 한 값이라 전체 리뷰 pool 규모에는
그대로 쓰지 않는다.

metric="euclidean"을 쓰는 이유: embedding.py의 embed()가 normalize_embeddings=True로
L2 정규화된 벡터를 생성하므로, 정규화된 벡터 사이에서는 euclidean 거리 순위가 cosine
거리 순위와 동일하다. sklearn HDBSCAN은 cosine을 기본 알고리즘(트리 기반)에서 직접
지원하지 않아 algorithm="brute"가 강제되므로, 결과가 같은 euclidean을 그대로 쓴다.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN

DEFAULT_MIN_CLUSTER_SIZE = 5
DEFAULT_MIN_SAMPLES = 3
DEFAULT_METRIC = "euclidean"
DEFAULT_MAX_FACETS = 2


@dataclass
class GlobalClusterResult:
    review_ids: list[str]
    book_ids: list[str]
    labels: np.ndarray  # 리뷰별 전역 클러스터 라벨, -1 = 노이즈
    centroids: dict[int, np.ndarray]  # {전역 cluster_label: centroid_vector}, 노이즈 제외


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
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    metric: str = DEFAULT_METRIC,
) -> GlobalClusterResult:
    """책 구분 없이 전체 리뷰 임베딩을 한 번에 클러스터링한다.

    책 간에 "결"의 기준을 공유하기 위한 단계이므로, 여기서 book_ids는 결과를 각
    책으로 다시 나눠 돌려주기 위한 딱지일 뿐, 클러스터링 자체에는 관여하지 않는다.
    """
    if len(embeddings) < min_cluster_size:
        labels = np.full(len(embeddings), -1)
    else:
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric=metric,
        )
        labels = clusterer.fit_predict(embeddings)

    centroids: dict[int, np.ndarray] = {}
    for label in sorted(set(labels)):
        if label == -1:
            continue
        mask = labels == label
        centroids[label] = embeddings[mask].mean(axis=0)

    return GlobalClusterResult(
        review_ids=review_ids, book_ids=book_ids, labels=labels, centroids=centroids
    )


def compute_book_identities(
    result: GlobalClusterResult,
    min_weight: float = 0.0,
    max_facets: int | None = DEFAULT_MAX_FACETS,
) -> dict[str, BookIdentity]:
    """전역 클러스터링 결과를 책 단위로 집계한다 (평균 없이 (centroid, weight) 리스트).

    min_weight: 이 값 미만인 weight를 가진 결은 신뢰도가 낮다고 보고 걸러낸다.
    기본값 0.0(필터링 없음) - 실제 임계값은 아직 미정 (DESIGN.md 7절).

    max_facets: 책마다 남기는 결의 최대 개수. weight가 높은 순으로 상위 max_facets개만
    남기고 나머지는 버린다. "결이 많은 책일수록 max-similarity 매칭에서 구조적으로
    유리해지는" 문제를 완화하기 위함 (자세한 근거는 모듈 docstring 참고). None이면
    제한 없음.
    """
    review_counts: Counter[str] = Counter(result.book_ids)
    label_counts: dict[str, Counter[int]] = {}

    for book_id, label in zip(result.book_ids, result.labels):
        if label == -1:
            continue
        label_counts.setdefault(book_id, Counter())[label] += 1

    identities: dict[str, BookIdentity] = {}
    for book_id in sorted(review_counts):
        identity = BookIdentity(book_id=book_id)
        total = review_counts[book_id]
        weights = {
            label: count / total
            for label, count in label_counts.get(book_id, Counter()).items()
            if count / total >= min_weight
        }
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

    # 주의: 여기서는 데모용으로 min_cluster_size=3, min_samples=2를 쓴다 (기본값
    # 5/3은 440개 실 데이터 규모를 가정한 값). 이 mock 데이터(45개 리뷰, 5권)는
    # 애초에 책 단위 클러스터링 검증용으로 책마다 소재를 뚜렷이 다르게 써서,
    # 기본값 5/3으로는 전부 노이즈 처리된다 (아래 실행 결과 뒤 설명 참고).
    demo_min_cluster_size, demo_min_samples = 3, 2
    result = global_cluster(
        review_ids, book_ids, embeddings,
        min_cluster_size=demo_min_cluster_size, min_samples=demo_min_samples,
    )
    identities = compute_book_identities(result)

    print(
        f"[데모 파라미터: min_cluster_size={demo_min_cluster_size}, "
        f"min_samples={demo_min_samples} (기본값 5/3은 이 mock 규모엔 너무 엄격해 "
        f"전부 노이즈 처리됨 - 실 데이터 440개 규모에서 재검증 필요)]"
    )
    print(f"전체 리뷰 {len(review_ids)}개 -> 전역 클러스터 {len(result.centroids)}개 발견\n")

    by_book: dict[str, list[tuple[str, int]]] = {}
    for rid, bid, label in zip(result.review_ids, result.book_ids, result.labels):
        by_book.setdefault(bid, []).append((rid, label))

    for book_id in sorted(by_book):
        print(f"=== {book_id} {title_map[book_id]} ===")
        for rid, label in by_book[book_id]:
            cluster_str = "노이즈" if label == -1 else f"전역 cluster {label}"
            print(f"  {rid} ({mock_label_map[rid]:>2}) -> {cluster_str}")
        identity = identities[book_id]
        print(f"  이 책이 걸쳐 있는 결(전역 클러스터) 수: {len(identity.cluster_vectors)}")
        for label, weight in sorted(identity.cluster_weights.items(), key=lambda x: -x[1]):
            print(f"    cluster {label}: weight={weight:.2f}")
        print()
