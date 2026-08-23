"""Phase 4 — 유저 취향 벡터와 책의 여러 아이덴티티 벡터를 매칭해 Top-K를 뽑는다.

DESIGN.md 5.Phase 4 참고:
- 선호 벡터 ↔ 책의 여러 아이덴티티 벡터 각각과 코사인 유사도 계산 -> max-similarity
- 기피 벡터 ↔ 책의 여러 아이덴티티 벡터도 동일하게 max-similarity 계산
  -> 페널티 가중치(λ)를 곱해서 최종 점수에서 차감
    score = max_sim(선호벡터, 책벡터들) - λ * max_sim(기피벡터, 책벡터들)
- 전체 책 점수 정렬 -> Top-K 반환

이 모듈은 Phase 2(clustering.py의 BookIdentity)가 어떤 클러스터링 알고리즘으로
만들어졌는지 몰라도 동작한다 - book.vectors()로 벡터 리스트만 받으면 되기 때문에,
나중에 HDBSCAN/KMeans 중 무엇으로 결정되어도 이 파일은 수정할 필요가 없다.

책의 아이덴티티 벡터가 하나도 없는 경우(리뷰가 전부 노이즈 처리됐거나 아직
클러스터링이 안 된 경우) max-similarity는 0으로 처리한다 - 이런 책은 Phase 6
(콜드스타트)에서 줄거리 임베딩으로 대체하는 게 원래 설계이므로, 여기서는
"이 책에 대한 근거가 없다"는 중립값만 반환하고 폴백 자체는 다루지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from clustering import BookIdentity
from user_profile import UserProfileVectors

DEFAULT_LAMBDA = 0.5


def cosine_max_sim(vector: np.ndarray, candidates: list[np.ndarray]) -> float:
    """vector와 candidates 중 가장 유사한 것의 코사인 유사도. 후보가 없거나
    vector가 영벡터(예: 기피 항목 없음)면 0.0을 반환한다.

    embed()가 normalize_embeddings=True로 벡터를 정규화해서 주므로, 코사인
    유사도는 내적(dot product)만으로 계산된다.
    """
    if not candidates or np.linalg.norm(vector) == 0:
        return 0.0
    return max(float(np.dot(vector, c)) for c in candidates)


def score_book(
    user: UserProfileVectors, book: BookIdentity, lam: float = DEFAULT_LAMBDA
) -> float:
    book_vectors = book.vectors()
    preferred_sim = cosine_max_sim(user.preferred_vector, book_vectors)
    avoided_sim = (
        cosine_max_sim(user.avoided_vector, book_vectors) if user.has_avoided else 0.0
    )
    return preferred_sim - lam * avoided_sim


def rank_books(
    user: UserProfileVectors,
    book_identities: dict[str, BookIdentity],
    k: int = 10,
    lam: float = DEFAULT_LAMBDA,
) -> list[tuple[str, float]]:
    """전체 책 점수를 매겨 내림차순 정렬한 (book_id, score) Top-K 리스트를 반환한다.

    DESIGN.md 3절의 최종 recommend(user_id, k) -> list[str] 인터페이스는
    book_id만 반환하지만, 이 모듈은 디버깅/평가에 필요한 score도 같이 준다.
    최종 조립(aspect_based_model.py)에서 [book_id for book_id, _ in rank_books(...)]
    로 뽑아 쓰면 된다.
    """
    scored = [
        (book_id, score_book(user, identity, lam))
        for book_id, identity in book_identities.items()
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


def rank_by_vector(
    query_vector: np.ndarray,
    book_identities: dict[str, BookIdentity],
    exclude_book_id: str | None = None,
    k: int = 10,
) -> list[tuple[str, float]]:
    """유저 프로필(선호/기피 페널티)이 아니라 임의의 단일 쿼리 벡터 기준으로 책을
    max-similarity 순 정렬한다. '이 리뷰와 결이 비슷한 책'처럼 선호/기피 개념이
    없는 쿼리(리뷰 임베딩 자체)에 쓴다 — rank_books()는 UserProfileVectors 전용이라
    이 용도에는 타입이 맞지 않는다.

    exclude_book_id로 원본 리뷰가 속한 책을 후보에서 제외한다. cosine_max_sim이
    후보 벡터가 없으면 0.0을 반환하므로, 결이 0개인 책은 별도 분기 없이 자연스럽게
    순위 하위로 밀린다.
    """
    scored = [
        (book_id, cosine_max_sim(query_vector, identity.vectors()))
        for book_id, identity in book_identities.items()
        if book_id != exclude_book_id
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


if __name__ == "__main__":
    import json

    from embedding import load_embeddings
    from clustering import global_cluster, compute_book_identities
    from user_profile import build_user_profiles

    # Phase 2: mock 데이터로 책 아이덴티티 생성 (데모 파라미터는 clustering.py와 동일 -
    # mock_data는 책 단위 검증용으로 만들어져 기본값 5/3으론 노이즈만 나오기 때문)
    embeddings_path = Path(__file__).parent / "mock_data" / "embeddings.npz"
    book_ids, review_ids, sentences, embeddings = load_embeddings(embeddings_path)
    # 데모용 n_clusters=6: mock 데이터(45개 리뷰)에는 기본값 30이 너무 크다 (clustering.py 참고)
    cluster_result = global_cluster(review_ids, book_ids, embeddings, n_clusters=6)
    book_identities = compute_book_identities(cluster_result)

    reviews_path = Path(__file__).parent / "mock_data" / "reviews.json"
    with open(reviews_path, encoding="utf-8") as f:
        book_data = json.load(f)
    title_map = {b["book_id"]: b["title"] for b in book_data["books"]}

    print("=== Phase 2 산출물: 책별 결(클러스터) 수 ===")
    for book_id, identity in sorted(book_identities.items()):
        print(f"  {book_id} {title_map[book_id]}: 결 {len(identity.cluster_vectors)}개")

    # Phase 3: mock 유저 프로필
    users_path = Path(__file__).parent / "mock_data" / "user_profiles.json"
    with open(users_path, encoding="utf-8") as f:
        users = json.load(f)
    profiles = build_user_profiles(users)

    print("\n=== Phase 4: 유저별 Top-5 추천 ===")
    for user in users:
        profile = profiles[user["userId"]]
        ranked = rank_books(profile, book_identities, k=5)
        print(f"\n[{user['userId']}] 선호={user['preferredEmotions']} 기피={user['avoidedTraits'] or '없음'}")
        for rank, (book_id, score) in enumerate(ranked, start=1):
            print(f"  {rank}. {book_id} {title_map[book_id]}  score={score:.4f}")
