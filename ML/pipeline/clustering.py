"""Phase 2 — 책 단위로 리뷰 임베딩을 HDBSCAN 클러스터링해 아이덴티티 벡터(결)를 뽑는다.

DESIGN.md 5.Phase 2 참고:
- 입력: 한 책에 속한 리뷰 임베딩들 (책 간 절대 섞이지 않음, 책 단위로 독립 수행)
- 방법: HDBSCAN (min_cluster_size=3부터 시작, 조정 가능)
- 출력: 클러스터별 centroid 벡터 리스트 = 그 책의 "결"들

min_samples=2로 min_cluster_size(3)와 분리해서 낮춘 이유: mock 데이터 실험(N=9, 호4/
불호4/혼재1)에서 기본값(min_samples=min_cluster_size=3)은 전부 노이즈로 무너졌지만,
min_samples=2에서는 호/불호가 섞이지 않는 순수한 2클러스터가 나왔다. min_samples가
낮을수록 "밀집됐다"고 인정하는 기준이 관대해져, 표본이 적은 상황에서도 국소 밀집
구조를 더 잘 잡아낸다 (자세한 실험 기록은 대화 로그 참고, DESIGN.md 7절에도 기록 예정).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN

DEFAULT_MIN_CLUSTER_SIZE = 3
DEFAULT_MIN_SAMPLES = 2


@dataclass
class ClusterResult:
    book_id: str
    review_ids: list[str]
    labels: np.ndarray  # 리뷰별 클러스터 라벨, -1 = 노이즈(어느 결에도 안 묶임)
    centroids: dict[int, np.ndarray]  # {cluster_label: centroid_vector}, 노이즈 제외


def cluster_book(
    book_id: str,
    review_ids: list[str],
    embeddings: np.ndarray,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> ClusterResult:
    """한 책에 속한 리뷰 임베딩만 입력받아 독립적으로 클러스터링한다.

    호출하는 쪽(cluster_all_books)이 이미 book_id로 필터링해서 넘기므로,
    이 함수 내부에서는 책 간 데이터가 섞일 여지가 없다.
    """
    if len(embeddings) < min_cluster_size:
        # 표본 수가 min_cluster_size 미만이면 애초에 클러스터를 만들 수 없어 전부 노이즈 처리
        labels = np.full(len(embeddings), -1)
    else:
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings)

    centroids: dict[int, np.ndarray] = {}
    for label in sorted(set(labels)):
        if label == -1:
            continue
        mask = labels == label
        centroids[label] = embeddings[mask].mean(axis=0)

    return ClusterResult(
        book_id=book_id, review_ids=review_ids, labels=labels, centroids=centroids
    )


def cluster_all_books(
    book_ids: list[str],
    review_ids: list[str],
    embeddings: np.ndarray,
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict[str, ClusterResult]:
    """책 단위로 독립 수행 -> {book_id: ClusterResult}.

    DESIGN.md: "책 간 절대 섞이지 않음" 규칙을 지키기 위해, 책마다 임베딩을
    잘라내 별도로 cluster_book을 호출한다 (전체를 한 번에 클러스터링하지 않음).
    """
    results: dict[str, ClusterResult] = {}
    for book_id in sorted(set(book_ids)):
        idx = [i for i, b in enumerate(book_ids) if b == book_id]
        results[book_id] = cluster_book(
            book_id,
            [review_ids[i] for i in idx],
            embeddings[idx],
            min_cluster_size,
            min_samples,
        )
    return results


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

    results = cluster_all_books(book_ids, review_ids, embeddings)

    for book_id, result in results.items():
        print(f"\n=== {book_id} {title_map[book_id]} ===")
        for rid, label in zip(result.review_ids, result.labels):
            cluster_str = "노이즈" if label == -1 else f"cluster {label}"
            print(f"  {rid} ({mock_label_map[rid]:>2}) -> {cluster_str}")
        print(f"  결(클러스터) 수: {len(result.centroids)}")
