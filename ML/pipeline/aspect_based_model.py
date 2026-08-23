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

## 유저 프로필 소스

팀원 4명이 구글폼으로 응답한 실제 `ML/eval/eval_data/eval_users.json`을 쓴다
(스키마가 `userId/preferredEmotions/avoidedTraits`로 evaluation.py의
load_eval_users()가 기대하는 것과 동일). mock_data/user_profiles.json은
Phase 3~6 단위 테스트/데모용으로 남겨두고, 최종 조립에서는 더 이상 안 쓴다.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from clustering import BookIdentity, GlobalClusterResult, compute_book_identities, global_cluster
from coldstart import augment_book_identities, load_book_descriptions
from embedding import embed_reviews
from matching import DEFAULT_LAMBDA, cosine_max_sim
from user_profile import UserProfileVectors, build_user_profiles
from xai import build_review_embedding_index

DATA_PROCESSED_DIR = Path(__file__).parent.parent.parent / "data" / "processed"
STRUCTURED_REVIEWS_PATH = DATA_PROCESSED_DIR / "structured_reviews.jsonl"
DEFAULT_USER_RECORDS_PATH = (
    Path(__file__).parent.parent / "eval" / "eval_data" / "eval_users.json"
)

# 백엔드와 동일한 로컬 개발 기본값(backend/app/config.py의 database_url 기본값과 동일) —
# ops가 두 서비스에 같은 DATABASE_URL 값을 그대로 재사용할 수 있도록 SQLAlchemy 스타일
# ("postgresql+psycopg://...") 표기를 기본값으로 두고, psycopg에 넘기기 전에 정규화한다.
DEFAULT_DATABASE_URL = "postgresql+psycopg://literec:literec@localhost:5432/literec"


@dataclass
class CatalogBundle:
    vectors_by_book: dict[str, list[np.ndarray]]  # recommend()용 (콜드스타트 결 포함)
    book_identities: dict[str, BookIdentity]  # explain용 (콜드스타트 미포함)
    cluster_result: GlobalClusterResult  # xai.describe_facet()이 요구
    review_embeddings: dict[str, np.ndarray]  # xai.find_medoid_review_id()가 요구
    reviews_by_id: dict[str, dict]  # xai.describe_facet()이 요구


_catalog_bundle_cache: CatalogBundle | None = None
_user_profiles_cache: dict[str, UserProfileVectors] | None = None


def _load_structured_reviews(path: Path = STRUCTURED_REVIEWS_PATH) -> list[dict]:
    reviews = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            reviews.append(json.loads(line))
    return reviews


def build_catalog_bundle() -> CatalogBundle:
    """Phase 1(임베딩) -> Phase 2(클러스터링) -> Phase 6(콜드스타트)를 순서대로
    실행해, recommend()용 벡터와 explain용 클러스터링 산출물을 함께 만든다.
    """
    reviews = _load_structured_reviews()
    # 정적 시드(440건) + DB에 쌓인 신규 구조화 리뷰(review_axes, STEP8 CronJob이 채움)를 합친다.
    # review_id 형식이 서로 달라(jsonl: "{isbn}_{review_index}" / DB: UUID) 충돌 위험 없음.
    reviews = reviews + load_db_structured_reviews(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    reviews_by_id = {r["review_id"]: r for r in reviews}
    review_ids = [r["review_id"] for r in reviews]
    book_ids = [r["book_id"] for r in reviews]

    _, embeddings = embed_reviews(reviews)
    review_embeddings = build_review_embedding_index(review_ids, embeddings)

    cluster_result = global_cluster(review_ids, book_ids, embeddings)
    book_identities = compute_book_identities(cluster_result)

    descriptions = load_book_descriptions()
    review_counts = Counter(book_ids)
    vectors_by_book = augment_book_identities(book_identities, descriptions, review_counts)

    return CatalogBundle(
        vectors_by_book=vectors_by_book,
        book_identities=book_identities,
        cluster_result=cluster_result,
        review_embeddings=review_embeddings,
        reviews_by_id=reviews_by_id,
    )


def build_catalog() -> dict[str, list[np.ndarray]]:
    """기존 시그니처 유지 — ML/eval/evaluation.py가 그대로 쓸 수 있도록.
    내부적으로 build_catalog_bundle()을 한 번만 계산해 재사용한다.
    """
    return build_catalog_bundle().vectors_by_book


def build_user_profile_index(
    path: Path = DEFAULT_USER_RECORDS_PATH,
) -> dict[str, UserProfileVectors]:
    """`ML/eval/tune_lambda.py` 등 오프라인 평가 스크립트가 그대로 쓰는 시그니처 —
    eval_users.json(팀원 4명)만 읽는다. DB 조회는 하지 않는다."""
    with open(path, encoding="utf-8") as f:
        users = json.load(f)
    return build_user_profiles(users)


def _to_psycopg_dsn(database_url: str) -> str:
    """SQLAlchemy 스타일 드라이버 접미사("postgresql+psycopg://...")를 psycopg가
    바로 이해하는 plain "postgresql://..." 형태로 정규화한다."""
    scheme, _, rest = database_url.partition("://")
    return f"{scheme.split('+', 1)[0]}://{rest}" if "+" in scheme else database_url


def load_db_users(database_url: str) -> list[dict]:
    """백엔드 DB(users/user_profiles)에서 온보딩을 마친 실제 유저를
    build_user_profiles()가 기대하는 스키마(userId/preferredEmotions/avoidedTraits)로
    변환해 가져온다. DB에 연결할 수 없으면(로컬에서 DB 없이 띄운 경우 등) 조용히
    빈 리스트를 반환한다 — ML 서버가 DB 없이도 기동은 되어야 한다."""
    try:
        import psycopg
    except ImportError:
        return []

    try:
        with psycopg.connect(_to_psycopg_dsn(database_url), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT u.id, up.preferred_emotions, up.avoided_traits "
                    "FROM user_profiles up JOIN users u ON u.id = up.user_id"
                )
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001 — DB 미기동/네트워크 문제 등 어떤 이유든 기동을 막지 않음
        print(f"[aspect_based_model] DB 유저 프로필 로드 실패, eval_users.json만 사용: {exc}")
        return []

    return [
        {
            "userId": str(user_id),
            "preferredEmotions": preferred_emotions or [],
            "avoidedTraits": avoided_traits or [],
        }
        for user_id, preferred_emotions, avoided_traits in rows
    ]


def load_db_structured_reviews(database_url: str) -> list[dict]:
    """review_axes(STEP8 CronJob이 채우는 5축 구조화 결과)를 _load_structured_reviews()와
    동일한 shape(book_id/review_id/5축 Korean 키)으로 변환해 가져온다. load_db_users()와
    동일하게 DB에 연결할 수 없으면 조용히 빈 리스트를 반환한다 — 카탈로그 빌드를 막지 않음."""
    try:
        import psycopg
    except ImportError:
        return []

    try:
        with psycopg.connect(_to_psycopg_dsn(database_url), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.id, r.isbn, a.emotion_experience, a.liked_elements, "
                    "a.disliked_elements, a.themes, a.reading_context "
                    "FROM review_axes a JOIN reviews r ON r.id = a.review_id"
                )
                rows = cur.fetchall()
    except Exception as exc:  # noqa: BLE001 — DB 미기동/네트워크 문제 등 어떤 이유든 기동을 막지 않음
        print(f"[aspect_based_model] DB 구조화 리뷰 로드 실패, 정적 시드만 사용: {exc}")
        return []

    return [
        {
            "book_id": isbn,
            "review_id": str(review_id),
            "정서_경험": emotion_experience,
            "좋았던_요소": liked_elements,
            "별로였던_요소": disliked_elements,
            "소재_및_주제": themes,
            "독서_경험_맥락": reading_context,
        }
        for review_id, isbn, emotion_experience, liked_elements, disliked_elements, themes, reading_context in rows
    ]


def build_full_profile_index(
    eval_users_path: Path = DEFAULT_USER_RECORDS_PATH,
    database_url: str | None = None,
) -> dict[str, UserProfileVectors]:
    """eval_users.json(오프라인 평가용) + 백엔드 DB의 실제 온보딩 유저를 합쳐 캐시를 만든다.

    ML 서버 프로세스가 재시작되면 메모리 캐시(_user_profiles_cache)가 초기화되는데,
    그동안 POST /profile/build로 등록됐던 실제 유저 프로필은 어디에도 영속화되지
    않아 함께 사라진다 — 이미 온보딩을 마친 유저도 서버 재시작 직후엔 recommend()가
    빈 리스트를 반환하는 문제가 있었다. 시작 시점에 백엔드 DB에서 다시 채워 넣어 방지한다.
    """
    profiles = build_user_profile_index(eval_users_path)

    url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    db_users = load_db_users(url)
    if db_users:
        profiles.update(build_user_profiles(db_users))
    return profiles


def ensure_catalog_loaded(force_rebuild: bool = False) -> CatalogBundle:
    """ML/serving/main.py가 카탈로그 캐시를 읽고 쓰는 유일한 통로.
    모듈 전역(_catalog_bundle_cache)을 직접 import해서 쓰지 말 것 — import 시점의
    스냅샷이 고정되어 이후 갱신이 반영되지 않는다."""
    global _catalog_bundle_cache
    if _catalog_bundle_cache is None or force_rebuild:
        _catalog_bundle_cache = build_catalog_bundle()
    return _catalog_bundle_cache


def ensure_profiles_loaded(force_rebuild: bool = False) -> dict[str, UserProfileVectors]:
    """ML/serving/main.py가 유저 프로필 캐시를 읽고 쓰는 유일한 통로.
    eval_users.json + DB의 실제 온보딩 유저를 함께 로드한다(build_full_profile_index 참고)."""
    global _user_profiles_cache
    if _user_profiles_cache is None or force_rebuild:
        _user_profiles_cache = build_full_profile_index()
    return _user_profiles_cache


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
    """user_id를 받아 book_id Top-K 추천 리스트 반환 (DESIGN.md 3절 인터페이스).
    기존과 동일한 인터페이스 — 내부만 ensure_*_loaded()를 쓰도록 리팩터링했다."""
    bundle = ensure_catalog_loaded()
    profiles = ensure_profiles_loaded()

    profile = profiles.get(user_id)
    if profile is None:
        return []

    scored = [
        (book_id, _score(profile, vectors)) for book_id, vectors in bundle.vectors_by_book.items()
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
