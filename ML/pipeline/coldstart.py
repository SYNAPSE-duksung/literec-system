"""Phase 6 — 리뷰가 부족한 책의 아이덴티티를 줄거리/추천사 임베딩으로 보강한다.

DESIGN.md 5.Phase 6 참고:
- 책의 리뷰 수가 임계값(기본 5개) 미만이면 클러스터링을 시도하지 않음
- 대신 줄거리/추천사 임베딩으로 아이덴티티 벡터를 대체
- 리뷰 수가 늘어남에 따라 줄거리 임베딩 -> 리뷰 기반 임베딩으로 가중치를 슬라이딩

슬라이딩 함수(DESIGN.md 7절에 "베이지안 스무딩"으로만 언급되고 미정이던 부분)는
고전적인 empirical-Bayes shrinkage 형태로 구현한다:

    weight = k / (k + review_count)

k(스무딩 상수)는 기본적으로 review_count의 threshold와 같은 값을 쓴다.
- review_count=0 -> weight=1.0 (순수 줄거리 기반)
- review_count=k(리뷰가 "충분히 모였다"고 보는 지점) -> weight=0.5 (줄거리와
  리뷰 기반 결이 반반)
- review_count가 그보다 훨씬 커지면 weight는 계속 작아지며 0에 점근한다
  (리뷰가 아무리 많아져도 완전히 0이 되지는 않지만, 실질적 영향력은 무시할
  수준으로 작아짐)

matching.py나 BookIdentity 구조를 바꾸지 않고도 이 슬라이딩을 적용하는 방법:
콜드스타트 벡터를 "단위 벡터"가 아니라 "weight만큼 줄어든 벡터"로 만들어서, 책의
기존 결 벡터 리스트에 그냥 원소 하나로 추가한다. cosine_max_sim(matching.py)의
내적 계산이 이 벡터에 대해서는 자동으로 weight가 곱해진 유사도가 되므로, Phase 4가
다른 결과 동일하게 max 비교만 해도 가중치가 자연히 반영된다.

실 데이터에서 "줄거리"는 data/processed/books_naver.jsonl의 description 필드에서
가져온다 (같은 파일의 perplexity_review는 쓰지 않음 - 그건 독자 반응 요약이라
스포일러가 섞일 수 있고, 이미 리뷰 생성(data/src/llm_review/generate_llm_reviews.py)
에 참고 자료로 쓰인 소스라 리뷰 임베딩과 정보가 순환될 위험이 있음). book_id는
파이프라인 전체에서 isbn을 그대로 쓰므로(structure_reviews.py 참고) 별도 변환 없이
isbn을 key로 매핑한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from clustering import BookIdentity
from embedding import DEFAULT_MODEL_NAME, embed

DEFAULT_REVIEW_THRESHOLD = 5
DEFAULT_BOOKS_NAVER_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "books_naver.jsonl"


def coldstart_weight(review_count: int, k: int = DEFAULT_REVIEW_THRESHOLD) -> float:
    """리뷰 수가 늘어날수록 0에 점근하는 콜드스타트(줄거리 기반) 가중치."""
    return k / (k + review_count)


def coldstart_facet(
    summary: str,
    review_count: int,
    k: int = DEFAULT_REVIEW_THRESHOLD,
    model_name: str = DEFAULT_MODEL_NAME,
) -> np.ndarray:
    """줄거리/추천사를 임베딩한 뒤 콜드스타트 가중치만큼 줄인 벡터를 반환한다.

    반환값은 단위 벡터가 아니다(norm = weight <= 1) - Phase 4의 max-similarity가
    다른(단위 벡터인) 결 벡터들과 비교할 때 이 벡터의 기여도만 자연히 낮아지게
    하기 위해서다.
    """
    weight = coldstart_weight(review_count, k)
    summary_vector = embed([summary], model_name=model_name)[0]
    return weight * summary_vector


def augment_with_coldstart(
    review_based_vectors: list[np.ndarray],
    summary: str,
    review_count: int,
    k: int = DEFAULT_REVIEW_THRESHOLD,
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[np.ndarray]:
    """Phase 2가 만든 리뷰 기반 결 벡터 리스트에 콜드스타트 결 하나를 추가해서 반환한다.

    review_based_vectors가 비어 있어도(리뷰 수가 threshold 미만이라 클러스터링을
    아예 시도하지 않았거나, 리뷰는 있지만 전부 노이즈로 걸러진 경우) 항상 최소
    1개의 벡터를 보장한다 - Phase 4에서 후보가 하나도 없어 점수가 무조건 0으로
    나오는 상황을 막아준다.
    """
    facet = coldstart_facet(summary, review_count, k, model_name)
    return [*review_based_vectors, facet]


def load_book_descriptions(path: str | Path = DEFAULT_BOOKS_NAVER_PATH) -> dict[str, str]:
    """books_naver.jsonl에서 book_id(=isbn) -> 줄거리(description) 매핑을 읽는다."""
    descriptions: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            book = json.loads(line)
            descriptions[book["isbn"]] = book["description"]
    return descriptions


def compute_coldstart_facets(
    descriptions: dict[str, str],
    review_counts: dict[str, int],
    k: int = DEFAULT_REVIEW_THRESHOLD,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, np.ndarray]:
    """여러 책의 줄거리를 한 번에 배치 임베딩해서 콜드스타트 벡터를 만든다.

    (Phase 1의 embed_reviews처럼, 책마다 따로 embed()를 호출하면 호출 오버헤드가
    책 수만큼 쌓이므로 배치로 처리한다.)
    """
    book_ids = list(descriptions.keys())
    summary_vectors = embed([descriptions[b] for b in book_ids], model_name=model_name)
    return {
        book_id: coldstart_weight(review_counts.get(book_id, 0), k) * vector
        for book_id, vector in zip(book_ids, summary_vectors)
    }


def augment_book_identities(
    book_identities: dict[str, BookIdentity],
    descriptions: dict[str, str],
    review_counts: dict[str, int],
    k: int = DEFAULT_REVIEW_THRESHOLD,
    model_name: str = DEFAULT_MODEL_NAME,
) -> dict[str, list[np.ndarray]]:
    """카탈로그 전체를 대상으로 book_id -> 매칭용(콜드스타트 포함) 벡터 리스트를 만든다.

    descriptions에 없는 책(줄거리를 못 구한 경우)은 콜드스타트 없이 리뷰 기반
    벡터만 그대로 쓴다 - 리뷰마저 없으면 빈 리스트가 될 수 있으니(Phase 4에서
    점수 0으로 처리됨), 원칙적으로는 모든 책이 description을 갖고 있어야 한다.
    """
    coldstart_facets = compute_coldstart_facets(descriptions, review_counts, k, model_name)
    all_book_ids = set(book_identities) | set(descriptions)

    augmented: dict[str, list[np.ndarray]] = {}
    for book_id in all_book_ids:
        review_vectors = (
            book_identities[book_id].vectors() if book_id in book_identities else []
        )
        facet = coldstart_facets.get(book_id)
        augmented[book_id] = [*review_vectors, facet] if facet is not None else review_vectors
    return augmented


if __name__ == "__main__":
    print("=== 콜드스타트 가중치 슬라이딩 곡선 (threshold=5) ===")
    for n in [0, 1, 3, 5, 9, 20, 50]:
        w = coldstart_weight(n)
        print(f"  review_count={n:>3} -> weight={w:.3f}")

    print()
    print("=== mock 데이터로 Phase 4(matching.py)와 통합 데모 ===")

    from clustering import global_cluster, compute_book_identities
    from embedding import load_embeddings
    from matching import cosine_max_sim
    from user_profile import build_user_profiles

    embeddings_path = Path(__file__).parent / "mock_data" / "embeddings.npz"
    book_ids, review_ids, sentences, embeddings = load_embeddings(embeddings_path)
    cluster_result = global_cluster(review_ids, book_ids, embeddings, min_cluster_size=3, min_samples=2)
    book_identities = compute_book_identities(cluster_result)

    reviews_path = Path(__file__).parent / "mock_data" / "reviews.json"
    with open(reviews_path, encoding="utf-8") as f:
        book_data = json.load(f)
    title_map = {b["book_id"]: b["title"] for b in book_data["books"]}
    summary_map = {b["book_id"]: b["summary"] for b in book_data["books"]}
    review_counts = {
        book_id: sum(1 for r in book_data["reviews"] if r["book_id"] == book_id)
        for book_id in title_map
    }

    print("책별 리뷰 기반 결 개수 (콜드스타트 적용 전):")
    for book_id, identity in sorted(book_identities.items()):
        print(f"  {book_id} {title_map[book_id]}: 결 {len(identity.cluster_vectors)}개, 리뷰 수 {review_counts[book_id]}")

    # 콜드스타트로 보강한 벡터 리스트 생성 (책마다 리뷰 기반 결 + 콜드스타트 결 1개)
    augmented_vectors: dict[str, list[np.ndarray]] = {}
    for book_id, identity in book_identities.items():
        augmented_vectors[book_id] = augment_with_coldstart(
            identity.vectors(), summary_map[book_id], review_counts[book_id]
        )

    users_path = Path(__file__).parent / "mock_data" / "user_profiles.json"
    with open(users_path, encoding="utf-8") as f:
        users = json.load(f)
    profiles = build_user_profiles(users)

    print("\n=== b004(리뷰 9개지만 전부 노이즈 처리되어 결 0개)의 콜드스타트 전/후 비교 ===")
    target = "b004"
    for user in users:
        profile = profiles[user["userId"]]
        before_pref = cosine_max_sim(profile.preferred_vector, book_identities[target].vectors())
        after_pref = cosine_max_sim(profile.preferred_vector, augmented_vectors[target])
        print(f"  {user['userId']}: 콜드스타트 전 선호유사도={before_pref:.4f} -> 후={after_pref:.4f}")

    print(f"\n(참고: {target} {title_map[target]}는 리뷰가 9개로 threshold(5)보다 많지만,")
    print(" HDBSCAN이 전부 노이즈로 분류해 결이 0개였던 케이스 - 콜드스타트는 review_count")
    print(" 기준으로만 동작하므로 '이유를 막론하고 결이 없는 책'에도 그대로 적용된다.")
    print(f" review_count=9, k=5 -> weight={coldstart_weight(9):.3f}로 낮은 신뢰도로 반영됨)")

    print()
    print("=" * 60)
    print("=== 실 데이터(books_naver.jsonl) 연결 확인 ===")
    print("=" * 60)

    real_descriptions = load_book_descriptions()
    print(f"description 로드: {len(real_descriptions)}권")

    structured_path = (
        Path(__file__).parent.parent.parent / "data" / "processed" / "structured_reviews.jsonl"
    )
    real_review_counts: dict[str, int] = {}
    with open(structured_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            real_review_counts[r["book_id"]] = real_review_counts.get(r["book_id"], 0) + 1

    sample_isbns = list(real_descriptions.keys())[:3]
    real_facets = compute_coldstart_facets(
        {isbn: real_descriptions[isbn] for isbn in sample_isbns},
        real_review_counts,
    )
    for isbn in sample_isbns:
        n = real_review_counts.get(isbn, 0)
        vec = real_facets[isbn]
        print(
            f"  isbn={isbn} review_count={n} "
            f"weight={coldstart_weight(n):.3f} facet_norm={np.linalg.norm(vec):.3f} "
            f"description(앞 40자)={real_descriptions[isbn][:40]!r}"
        )
