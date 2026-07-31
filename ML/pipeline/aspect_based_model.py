"""최종 조립 — Phase 1/2/3/4/6 모듈을 묶어서 DESIGN.md 3절의

    def recommend(user_id: str, k: int = 10) -> list[str]

인터페이스를 구현한다. `ML/eval/evaluation.py`의
`evaluate_model(recommend_fn=recommend, ...)`에 그대로 꽂아 쓸 수 있도록
시그니처와 호출 방식(`recommend_fn(user_id, k)` -> `list[str]`)을 정확히
맞춘다 (evaluation.py는 유저 1명당 이 함수를 k=max(5,10,20)로 1번만 호출한다).

## 캐싱 전략

`evaluate_model()`이 유저마다 이 함수를 반복 호출하므로, 무거운 연산
(리뷰 임베딩, 전역 클러스터링, 콜드스타트 결 계산)은 **프로세스당 한 번만**
수행하고 모듈 전역에 캐싱한다 (`_catalog_cache`). 유저 프로필도 마찬가지로
한 번만 로드한다(`_user_profiles_cache`). `recommend()` 호출마다 새로 하는
일은 "이미 계산된 카탈로그에서 이 유저 벡터와 매칭 점수 계산"뿐이다.

## 유저 프로필 소스 (임시)

DESIGN.md가 참고하라고 한 `ML/eval/eval_data/eval_users.json`이 아직 팀원
쪽에도 존재하지 않는다 (`ML/eval/evaluation.py`도 자체 테스트를 synthetic
데이터로 돌리는 상태). 그래서 지금은 `DEFAULT_USER_RECORDS_PATH`를
`mock_data/user_profiles.json`으로 잡아둔다 - 실제 eval_users.json이 생기면
이 상수 하나만 바꾸면 된다(스키마가 `userId/preferredEmotions/avoidedTraits`로
이미 동일하다는 것을 evaluation.py의 load_eval_users()에서 확인함).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from clustering import compute_book_identities, global_cluster
from coldstart import augment_book_identities, load_book_descriptions
from embedding import embed_reviews
from matching import DEFAULT_LAMBDA, cosine_max_sim
from user_profile import UserProfileVectors, build_user_profiles

DATA_PROCESSED_DIR = Path(__file__).parent.parent.parent / "data" / "processed"
STRUCTURED_REVIEWS_PATH = DATA_PROCESSED_DIR / "structured_reviews.jsonl"
DEFAULT_USER_RECORDS_PATH = Path(__file__).parent / "mock_data" / "user_profiles.json"

_catalog_cache: dict[str, list[np.ndarray]] | None = None
_user_profiles_cache: dict[str, UserProfileVectors] | None = None


def _load_structured_reviews(path: Path = STRUCTURED_REVIEWS_PATH) -> list[dict]:
    reviews = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            reviews.append(json.loads(line))
    return reviews


def build_catalog() -> dict[str, list[np.ndarray]]:
    """Phase 1(임베딩) -> Phase 2(클러스터링) -> Phase 6(콜드스타트)를 순서대로
    실행해, book_id -> 매칭용 벡터 리스트(콜드스타트 결 포함)를 만든다.
    """
    reviews = _load_structured_reviews()
    review_ids = [r["review_id"] for r in reviews]
    book_ids = [r["book_id"] for r in reviews]

    _, embeddings = embed_reviews(reviews)

    cluster_result = global_cluster(review_ids, book_ids, embeddings)
    book_identities = compute_book_identities(cluster_result)

    descriptions = load_book_descriptions()
    review_counts = Counter(book_ids)

    return augment_book_identities(book_identities, descriptions, review_counts)


def build_user_profile_index(
    path: Path = DEFAULT_USER_RECORDS_PATH,
) -> dict[str, UserProfileVectors]:
    with open(path, encoding="utf-8") as f:
        users = json.load(f)
    return build_user_profiles(users)


def _score(
    profile: UserProfileVectors, vectors: list[np.ndarray], lam: float = DEFAULT_LAMBDA
) -> float:
    """matching.score_book()과 동일한 공식이지만, BookIdentity가 아니라 콜드스타트로
    보강된 순수 벡터 리스트를 입력으로 받는다 (augment_book_identities의 출력 형태).
    """
    preferred_sim = cosine_max_sim(profile.preferred_vector, vectors)
    avoided_sim = cosine_max_sim(profile.avoided_vector, vectors) if profile.has_avoided else 0.0
    return preferred_sim - lam * avoided_sim


def recommend(user_id: str, k: int = 10) -> list[str]:
    """user_id를 받아 book_id Top-K 추천 리스트 반환 (DESIGN.md 3절 인터페이스)."""
    global _catalog_cache, _user_profiles_cache

    if _catalog_cache is None:
        _catalog_cache = build_catalog()
    if _user_profiles_cache is None:
        _user_profiles_cache = build_user_profile_index()

    profile = _user_profiles_cache.get(user_id)
    if profile is None:
        return []

    scored = [
        (book_id, _score(profile, vectors)) for book_id, vectors in _catalog_cache.items()
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [book_id for book_id, _ in scored[:k]]


if __name__ == "__main__":
    import time

    with open(DEFAULT_USER_RECORDS_PATH, encoding="utf-8") as f:
        users = json.load(f)

    print("=== recommend() 첫 호출 (카탈로그+프로필 캐시 생성 포함) ===")
    t0 = time.time()
    first_result = recommend(users[0]["userId"], k=10)
    print(f"  소요 시간: {time.time() - t0:.1f}초")
    print(f"  [{users[0]['userId']}] Top-10: {first_result}")

    print("\n=== recommend() 이후 호출 (캐시 재사용, 훨씬 빨라야 함) ===")
    for user in users:
        t0 = time.time()
        result = recommend(user["userId"], k=10)
        elapsed = time.time() - t0
        print(
            f"  [{user['userId']}] 선호={user['preferredEmotions']} "
            f"기피={user['avoidedTraits'] or '없음'} ({elapsed:.3f}초)"
        )
        print(f"    Top-10: {result}")

    print("\n=== 존재하지 않는 user_id 처리 확인 (빈 리스트 반환해야 함) ===")
    print(f"  recommend('nonexistent_user', 5) = {recommend('nonexistent_user', 5)}")

    print("\n=== k 값에 따라 잘리는지 확인 ===")
    for k in [1, 5, 20]:
        print(f"  k={k}: {len(recommend(users[0]['userId'], k=k))}개 반환")
