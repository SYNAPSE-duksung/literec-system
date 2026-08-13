# ML 추천 API 연결 — 전체 작업 목록

> 기준: `ML_RECOMMENDATION_PIPELINE.md`  
> 목표: `recommend(user_id, k)` → 백엔드 `/api/recommendations` 실제 응답 연결  
> + DB 스키마 보완, 이벤트 로깅, CronJob 온라인 파이프라인

> **2026-08-12 정정**: STEP 0~2의 예시 코드가 실제 코드(백엔드 경로/타입, ML 파이프라인 함수 시그니처, 프론트엔드 구현 상태)와 여러 지점에서 어긋나 있어 전면 재검토했다. 무엇이 왜 바뀌었는지는 문서 맨 아래 [정합성 점검 결과](#정합성-점검-결과-2026-08-12) 섹션을 먼저 읽을 것. STEP 3 이후는 아직 실제 인프라 코드가 없어 큰 구조는 그대로 두되, STEP 1~2에서 바뀐 타입/경로만 맞춰 두었다 — **STEP 1 착수 전에 그 시점 코드 기준으로 다시 한 번 대조 필요.**

---

## 현재 상태

```
동작하는 것:
├── ML/pipeline/aspect_based_model.py
│   └── recommend(user_id, k=10) → list[str] (isbn) ✅
├── DB
│   ├── books 88권 ✅
│   ├── reviews 440건 ✅ (created_at 컬럼 존재 — 단, 값이 전부 "시드 스크립트 실행 시각"으로 잘못 찍혀 있음, 정합성 A 참고)
│   └── users/books PK 타입: users.id = UUID, books.isbn = String PK (정수 id 없음)
├── backend/app/routers/recommendations.py → GET /api/recommendations, GET /reviews/{id}/similar-books 둘 다 랜덤 더미로 이미 응답 중 (반환 스키마 RecommendationOut은 확정, 내부 로직만 더미)
└── 프론트엔드 → useRecommendations()/useReviews() 등 훅이 이미 실제 백엔드 HTTP 엔드포인트를 호출 중 (mock 아님). 리뷰 작성일(createdAt)과 XAI 설명(explanation)은 이미 화면에 렌더링되고 있음 — ReviewCard/ReviewDetailPage/XAINote 참고

연결 안 된 것:
├── backend ↔ ML 파이프라인 연결 없음 (recommendations.py가 ML 서버를 호출하지 않음)
├── 실제 DB 유저 → ML 프로필 변환 없음 (build_single_user_profile() 자체가 아직 없음)
├── ML 서버(FastAPI) 자체가 없음 — ML/serving/은 .gitkeep만 있는 빈 디렉터리
├── XAI 설명이 진짜 로직으로 채워지지 않음 (지금은 더미 문구)
├── reviews.is_processed 컬럼 없음
├── recommendation_events 테이블 없음
├── 추천 노출/클릭 이벤트 로깅이 프론트에 전혀 없음
└── CronJob 없음
```

---

## 아키텍처

```
사용자 요청
    ↓
backend (8000) ── HTTP ──▶ ml-server (8001)
    │                           │
    │                    recommend() 실행 (캐시)
    │                           │
    └── books DB 조회 ◀── isbn 리스트 반환
    └── 응답 조합 후 반환

주 단위 CronJob
    └── KMeans 재실행 → POST /admin/rebuild-catalog → 캐시 갱신
```

---

## 전체 작업 체크리스트 (진행 순서)

---

### STEP 0 — DB 스키마 보완 (Alembic 마이그레이션)

> **정정**: `reviews.created_at`은 `0001_initial_schema` 마이그레이션에 이미 있다(`backend/app/models/review.py`). 이번 STEP에서 컬럼을 새로 추가할 건 `is_processed` 하나뿐이다. 대신 기존 `created_at` **값**이 잘못 채워져 있는 문제(0-1b)가 있어 그걸 고친다.

**0-1. `reviews` 테이블에 `is_processed` 컬럼 추가**

- `is_processed`: CronJob이 처리 완료 여부 표시 (일 단위 임베딩 대상 필터링)

```python
# backend/alembic/versions/xxxx_add_reviews_is_processed.py
def upgrade():
    op.add_column('reviews',
        sa.Column('is_processed', sa.Boolean(), server_default='false', nullable=False))
    op.create_index('ix_reviews_is_processed', 'reviews', ['is_processed'])

def downgrade():
    op.drop_index('ix_reviews_is_processed', 'reviews')
    op.drop_column('reviews', 'is_processed')
```

> LLM 생성 리뷰(440건)는 `is_processed=TRUE`로 초기 적재.  
> 이후 게시판으로 유입되는 실사용자 리뷰는 컬럼 기본값(`server_default='false'`)을 그대로 써서 `FALSE`로 시작 — 별도 처리 불필요.

`backend/app/models/review.py`의 `Review` 모델에도 동일하게 컬럼 추가:

```python
is_processed: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
```

**0-1b. `reviews.created_at` 값 정정 — 시드 스크립트 수정 (신규)**

`backend/scripts/seed_data.py`는 `data/processed/llm_reviews.jsonl`(440건)을 적재할 때 `created_at`을 명시하지 않는다. 그 결과 컬럼의 `server_default=func.now()`가 적용되어, **440건 전부가 "시드 스크립트를 마지막으로 실행한 시각"**으로 찍힌다. 프론트(`ReviewCard`/`ReviewDetailPage`)는 이미 이 값을 그대로 렌더링하고 있으므로, 지금 상태로는 리뷰 440건이 전부 같은 날 같은 시각에 작성된 것처럼 보인다.

`llm_reviews.jsonl` 자체에는 작성 시각 필드가 없으므로, **이 파일이 최초로 리포지토리에 커밋된 시각**을 대신 사용한다(`git log --diff-filter=A --follow -- data/processed/llm_reviews.jsonl` → 커밋 `1c96df5`, **2026-07-26 23:28:11 +09:00**).

```python
# backend/scripts/seed_data.py
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
LLM_REVIEWS_SEED_CREATED_AT = datetime(2026, 7, 26, 23, 28, 11, tzinfo=KST)

# 리뷰 insert 시:
Review(
    isbn=row["isbn"],
    user_id=llm_bot_user_id,
    source="llm_generated",
    persona=row.get("persona"),
    content=row["content"],
    created_at=LLM_REVIEWS_SEED_CREATED_AT,
    is_processed=True,
    ...
)
```

이미 잘못된 `created_at`으로 적재된 행이 있다면 1회성 backfill로 고친다:

```sql
UPDATE reviews
SET created_at = '2026-07-26 23:28:11+09', is_processed = TRUE
WHERE source = 'llm_generated';
```

> 참고: `structured_reviews.jsonl`(5축 구조화본, 커밋 `599677d`, 2026-07-30)은 별도 파생 파일이며 `seed_data.py`가 읽지 않는다 — `reviews.created_at`과는 무관, ML 파이프라인 입력으로만 쓰인다.

> **프론트엔드 변경 불필요**: `Review.createdAt` 표시는 이미 `ReviewCard.tsx`/`ReviewDetailPage.tsx`에 구현되어 있다(`new Date(review.createdAt).toLocaleDateString('ko-KR')`). 이 STEP은 화면에 새 UI를 추가하는 게 아니라, 이미 있는 화면에 들어갈 **값을 바로잡는** 작업이다.

**0-2. `recommendation_events` 테이블 신규 생성**

CTR 및 온라인 피드백 집계를 위한 이벤트 로그 테이블.

> **정정**: `users.id`는 `UUID`(정수 아님), `books`는 정수 `id`가 없고 `isbn`(문자열)이 PK다(`backend/app/models/user.py`, `backend/app/models/book.py`). 아래 FK 타입을 실제 스키마에 맞게 고쳤다 — 원래 `sa.Integer()` FK로 작성하면 참조 대상 컬럼이 없어 마이그레이션이 실패한다.

```python
# backend/alembic/versions/xxxx_create_recommendation_events.py
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

def upgrade():
    op.create_table('recommendation_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('book_id', sa.String(), sa.ForeignKey('books.isbn'), nullable=False),
        sa.Column('event_type', sa.String(20), nullable=False),
        # 'impression' : 추천 목록에 노출
        # 'click'      : 추천 도서 상세 클릭
        # 'like'       : 좋아요
        # 'review'     : 리뷰 작성까지 전환
        sa.Column('source', sa.String(20), nullable=True),
        # 'home'          : 홈 추천 탭
        # 'book_detail'   : 책 상세 유사 추천
        # 'review_detail' : 리뷰 상세 유사 추천
        sa.Column('rank', sa.SmallInteger(), nullable=True),
        # 노출 시 추천 순위 (1위, 2위 ...) — impression 이벤트에만 사용
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_rec_events_user_id', 'recommendation_events', ['user_id'])
    op.create_index('ix_rec_events_created_at', 'recommendation_events', ['created_at'])
    op.create_index('ix_rec_events_event_type', 'recommendation_events', ['event_type'])

def downgrade():
    op.drop_table('recommendation_events')
```

**0-3. SQLAlchemy 모델 추가**

```python
# backend/app/models/recommendation_event.py
import uuid
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id    = Column(String, ForeignKey("books.isbn"), nullable=False)
    event_type = Column(String(20), nullable=False)
    source     = Column(String(20), nullable=True)
    rank       = Column(SmallInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

`backend/app/models/__init__.py`에 export 추가하는 것도 잊지 말 것(다른 모델들과 동일 패턴).

**0-4. 마이그레이션 실행 확인**

```bash
cd backend
alembic upgrade head
# reviews.is_processed 컬럼 확인
# recommendation_events 테이블 생성 확인

uv run python scripts/seed_data.py
# reviews.created_at이 2026-07-26 23:28:11+09로, is_processed가 TRUE로 찍히는지 확인
```

**체크리스트**
```
[ ] 0-1: reviews.is_processed 컬럼 마이그레이션 작성 + 실행 (+ 모델에 컬럼 추가)
[ ] 0-1b: seed_data.py가 LLM 리뷰 created_at을 커밋 시각으로 명시 설정하도록 수정 + backfill SQL 실행
[ ] 0-2: recommendation_events 테이블 마이그레이션 작성 + 실행 (UUID/String FK 타입 확인)
[ ] 0-3: SQLAlchemy 모델 파일 추가 (backend/app/models/recommendation_event.py)
[ ] 0-4: alembic upgrade head + 시드 재실행 로컬 확인
```

---

### STEP 1 — ML 서버 생성

> **정정**: 아래 원안은 실제 `ML/pipeline/aspect_based_model.py` / `xai.py` / `user_profile.py`와 맞지 않는 부분이 많아 전면 재작성했다. 핵심 문제 4가지:
> 1. `build_catalog()`는 파라미터가 없는 순수 함수라 `force_rebuild=True`를 넘기면 `TypeError`가 난다. "다시 계산"은 `build_catalog()` 자체가 아니라 **모듈 전역 캐시를 언제 무효화할지**의 문제다.
> 2. `_catalog_cache`/`_user_profiles_cache`는 `recommend()` 내부에서 `global`로만 채워진다. `lifespan()`에서 `build_catalog()`/`build_user_profile_index()`를 호출해도 두 캐시는 여전히 `None`이고, `from aspect_based_model import _catalog_cache`로 가져오면 그 시점의 `None` 스냅샷이 영원히 고정된다(`/health`가 항상 `false`). → **모듈을 통째로 import해서 캐시 접근용 함수를 통해서만 읽고 쓴다.**
> 3. `build_single_user_profile()`이 캐시에 넣어야 하는 건 `(prefer_vec, avoid_vec)` 튜플이 아니라 `UserProfileVectors` 데이터클래스 인스턴스다 — 아니면 `_score()`가 `profile.preferred_vector` 접근에서 크래시한다.
> 4. `explain_recommendation()`의 실제 시그니처는 `(user_vector, book_id, identity, result, review_embeddings, reviews_by_id)`다. `_catalog_cache`(`dict[book_id, list[vector]]`, 콜드스타트 벡터까지 평탄화됨)만으로는 이 인자들을 만들 수 없다 — 클러스터링 원본 산출물(`BookIdentity`, `GlobalClusterResult`, 리뷰 임베딩 인덱스, 리뷰 원문)을 캐시에 별도로 보존해야 한다.
>
> (사용자 결정) 프론트는 추천 카드마다 지연 호출 없이 `useRecommendations()` 응답 하나로 `hookLine`/`matchedTrait`/`explanation`을 바로 그리므로, `/recommend`가 스코어링과 동시에 상위 K권의 설명까지 배치로 함께 반환한다. 문서 원안의 별도 `/explain` 엔드포인트는 (백엔드가 K번 순차 호출하는 대신) **내부적으로만 재사용**하는 형태로 남긴다.

**1-1. `ML/pipeline/aspect_based_model.py` 수정 — 캐시를 명시적 접근자 함수로, 클러스터링 산출물도 함께 보존**

```python
# ML/pipeline/aspect_based_model.py
from dataclasses import dataclass

@dataclass
class CatalogBundle:
    vectors_by_book: dict[str, list[np.ndarray]]      # 기존 build_catalog() 반환값 (recommend용, 콜드스타트 포함)
    book_identities: dict[str, BookIdentity]           # Phase 2 산출물 (explain용, 콜드스타트 미포함)
    cluster_result: GlobalClusterResult                 # xai.describe_facet()이 요구
    review_embeddings: dict[str, np.ndarray]            # xai.find_medoid_review_id()가 요구
    reviews_by_id: dict[str, dict]                      # xai.describe_facet()이 요구

_catalog_bundle_cache: CatalogBundle | None = None
_user_profiles_cache: dict[str, UserProfileVectors] | None = None


def build_catalog_bundle() -> CatalogBundle:
    reviews = _load_structured_reviews()
    reviews_by_id = {r["review_id"]: r for r in reviews}
    review_ids = [r["review_id"] for r in reviews]
    book_ids = [r["book_id"] for r in reviews]

    _, embeddings = embed_reviews(reviews)
    review_embeddings = {rid: embeddings[i] for i, rid in enumerate(review_ids)}

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
    내부적으로 build_catalog_bundle()을 한 번만 계산해 재사용한다."""
    return build_catalog_bundle().vectors_by_book


def ensure_catalog_loaded(force_rebuild: bool = False) -> CatalogBundle:
    """ML/serving/main.py가 캐시를 읽고 쓰는 유일한 통로. 모듈 전역을 직접 import하지 말 것."""
    global _catalog_bundle_cache
    if _catalog_bundle_cache is None or force_rebuild:
        _catalog_bundle_cache = build_catalog_bundle()
    return _catalog_bundle_cache


def ensure_profiles_loaded(force_rebuild: bool = False) -> dict[str, UserProfileVectors]:
    global _user_profiles_cache
    if _user_profiles_cache is None or force_rebuild:
        _user_profiles_cache = build_user_profile_index()
    return _user_profiles_cache


def recommend(user_id: str, k: int = 10) -> list[str]:
    """기존과 동일한 인터페이스 — 내부만 ensure_*_loaded()를 쓰도록 리팩터링."""
    bundle = ensure_catalog_loaded()
    profiles = ensure_profiles_loaded()

    profile = profiles.get(user_id)
    if profile is None:
        return []

    scored = [(bid, _score(profile, vectors)) for bid, vectors in bundle.vectors_by_book.items()]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [bid for bid, _ in scored[:k]]
```

`ML/eval/evaluation.py`가 `build_catalog()`를 직접 import해 쓰고 있다면 반환 타입(`dict[str, list[np.ndarray]]`)이 그대로이므로 수정 불필요.

**1-2. `ML/pipeline/user_profile.py` 수정**

단일 유저 프로필을 만드는 순수 함수 추가(캐시에 직접 쓰지 않음 — 캐시 mutation은 `main.py` 쪽 책임).

```python
def build_single_user_profile(
    user_id: str,
    preferred_emotions: list[str],
    avoided_traits: list[str],
) -> UserProfileVectors:
    """온보딩/마이페이지에서 넘어온 취향을 UserProfileVectors로 변환한다.
    build_user_profiles()와 동일한 문장화 규칙(to_preferred_sentence/to_avoided_sentence)을 재사용."""
    pref_sentence = to_preferred_sentence(preferred_emotions)
    avoid_sentence = to_avoided_sentence(avoided_traits)

    preferred_vector = embed([pref_sentence])[0] if pref_sentence else np.zeros(EMBEDDING_DIM, dtype=np.float32)
    has_avoided = bool(avoid_sentence)
    avoided_vector = embed([avoid_sentence])[0] if has_avoided else np.zeros(EMBEDDING_DIM, dtype=np.float32)

    return UserProfileVectors(
        user_id=user_id,
        preferred_vector=preferred_vector,
        avoided_vector=avoided_vector,
        has_avoided=has_avoided,
    )
```

**1-3. `ML/pipeline/xai.py` — 배치 설명 헬퍼 추가**

기존 `explain_recommendation()`/`format_reason()`은 그대로 두고, `/recommend`가 상위 K권을 한 번에 설명할 때 쓸 배치 함수를 추가한다. 책에 실제 결(cluster facet)이 하나도 없는 경우(순수 콜드스타트 대상)는 `explain_recommendation()`이 `None`을 반환하므로 그 경우의 대체 문구도 함께 정의한다.

```python
# ML/pipeline/xai.py
COLDSTART_FALLBACK_REASON = "아직 쌓인 리뷰는 적지만, 줄거리가 취향과 잘 맞는 책이에요."

# RADAR_TRAITS(app/src/constants/options.ts, backend RADAR_TRAITS와 동일한 5개 UI 표기 값)와
# ML 5축(AXES)은 서로 다른 어휘 체계라 1:1 매핑이 정의돼 있지 않다. matchedTrait는 현재
# 어떤 화면에서도 실제로 렌더링되지 않는 필드(UI_DESIGN_SPEC.md 5.1 타입에는 있지만 미사용)이므로,
# 정확한 취향축 매핑보다 "값이 존재하고 그럴듯하다"는 수준으로 잠정 매핑한다.
# 화면에 실제로 노출하게 되면 이 매핑을 다시 설계해야 한다.
AXIS_TO_RADAR_TRAIT = {
    "좋았던_요소": "몰입감",
    "정서_경험": "서정성",
    "소재_및_주제": "현실성",
    "독서_경험_맥락": "잔잔함",
}

def build_recommendation_explanation(
    user_vector: np.ndarray,
    book_id: str,
    identity: BookIdentity,
    result: GlobalClusterResult,
    review_embeddings: dict[str, np.ndarray],
    reviews_by_id: dict[str, dict],
) -> dict:
    """RecommendationOut(hookLine/matchedTrait/explanation)을 채우는 데 필요한 문구를 한 번에 만든다."""
    facet = None
    if identity.cluster_vectors:
        facet = explain_recommendation(
            user_vector, book_id, identity, result, review_embeddings, reviews_by_id
        )
    if facet is None:
        return {
            "hook_line": COLDSTART_FALLBACK_REASON,
            "matched_trait": "잔잔함",
            "explanation": COLDSTART_FALLBACK_REASON,
        }
    reason = format_reason(facet)
    matched_axis = next(
        (axis for axis in ["좋았던_요소", "정서_경험", "소재_및_주제", "독서_경험_맥락"]
         if facet["representative_content"].get(axis)),
        None,
    )
    return {
        "hook_line": reason,
        "matched_trait": AXIS_TO_RADAR_TRAIT.get(matched_axis, "몰입감"),
        "explanation": reason,
    }
```

**1-4. `ML/serving/main.py` 신규 작성**

엔드포인트 목록:

| 메서드 | 경로 | 역할 |
|---|---|---|
| `GET`  | `/health`                 | 헬스체크 (카탈로그/프로필 로드 여부 포함) |
| `POST` | `/recommend`              | 추천 + 상위 K권 XAI 설명을 배치로 함께 반환 |
| `POST` | `/profile/build`          | 유저 프로필 생성/갱신 (온보딩·마이페이지 연동) |
| `POST` | `/admin/rebuild-catalog`  | 카탈로그 캐시 강제 갱신 (CronJob 전용) |

```python
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ML.pipeline import aspect_based_model as abm
from ML.pipeline import xai
from ML.pipeline.user_profile import build_single_user_profile

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change-me")


@asynccontextmanager
async def lifespan(app: FastAPI):
    abm.ensure_catalog_loaded()
    abm.ensure_profiles_loaded()   # eval_users.json (오프라인 평가용 팀원 4명) — 실제 유저는 /profile/build로 추가됨
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "catalog_loaded": abm._catalog_bundle_cache is not None,
        "profiles_loaded": abm._user_profiles_cache is not None,
    }


class RecommendRequest(BaseModel):
    user_id: str
    k: int = 10


class RecommendedBookOut(BaseModel):
    book_id: str
    hook_line: str
    matched_trait: str
    explanation: str


@app.post("/recommend", response_model=list[RecommendedBookOut])
def get_recommendations(req: RecommendRequest):
    profiles = abm.ensure_profiles_loaded()
    profile = profiles.get(req.user_id)
    if profile is None:
        return []

    bundle = abm.ensure_catalog_loaded()
    book_ids = abm.recommend(req.user_id, k=req.k)

    results = []
    for book_id in book_ids:
        identity = bundle.book_identities.get(book_id)
        explanation = xai.build_recommendation_explanation(
            profile.preferred_vector, book_id, identity,
            bundle.cluster_result, bundle.review_embeddings, bundle.reviews_by_id,
        ) if identity is not None else {
            "hook_line": xai.COLDSTART_FALLBACK_REASON,
            "matched_trait": "잔잔함",
            "explanation": xai.COLDSTART_FALLBACK_REASON,
        }
        results.append(RecommendedBookOut(book_id=book_id, **explanation))
    return results


class BuildProfileRequest(BaseModel):
    user_id: str
    preferred_emotions: list[str]
    avoided_traits: list[str]


@app.post("/profile/build")
def build_profile(req: BuildProfileRequest):
    profile = build_single_user_profile(req.user_id, req.preferred_emotions, req.avoided_traits)
    profiles = abm.ensure_profiles_loaded()
    profiles[req.user_id] = profile   # 같은 dict를 in-place로 갱신 — 재조회 시 바로 반영됨
    return {"status": "ok"}


@app.post("/admin/rebuild-catalog")
def rebuild_catalog(x_admin_secret: str = Header(...)):
    """주 단위 CronJob이 KMeans 재실행 후 이 엔드포인트를 호출해 캐시를 갱신.
    ADMIN_SECRET 헤더 불일치 시 403 반환."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    abm.ensure_catalog_loaded(force_rebuild=True)
    return {"status": "ok"}
```

> `ADMIN_SECRET`은 K8s Secret으로 주입. 외부에 노출되지 않도록 Ingress에서  
> `/admin/*` 경로를 외부 차단하거나, ClusterIP Service만 사용.

> `ML/pyproject.toml`에 `fastapi`, `uvicorn`, `httpx`(관리용 스크립트/cron에서 백엔드 호출 시)를 의존성으로 추가해야 한다 — 현재 `numpy`, `sentence-transformers`만 있음.

**1-5. `ML/serving/Dockerfile` 작성**

```dockerfile
FROM python:3.11-slim
WORKDIR /app

RUN pip install uv

COPY ML/pyproject.toml ML/uv.lock ./
RUN uv sync --frozen

COPY ML/ ./ML/
COPY data/processed/ ./data/processed/

EXPOSE 8001
CMD ["uv", "run", "uvicorn", "ML.serving.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

> `data/processed/structured_reviews.jsonl`, `books_naver.jsonl`이 이미지에 포함되어야 함.  
> 데이터 경로 하드코딩 여부 확인 → 환경변수(`DATA_DIR`)로 교체 권장.

**1-6. 로컬 단독 실행 확인**

```bash
cd /path/to/repo
uvicorn ML.serving.main:app --port 8001

# 헬스체크
curl localhost:8001/health

# 추천 테스트 (eval_users.json의 user_id 중 하나 사용) — 응답이 book_id 리스트가 아니라
# {book_id, hook_line, matched_trait, explanation} 객체 리스트임에 주의
curl -X POST localhost:8001/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": "팀원_user_id", "k": 5}'
```

**체크리스트**
```
[ ] 1-1: aspect_based_model.py에 CatalogBundle/ensure_catalog_loaded/ensure_profiles_loaded 추가 (build_catalog() 시그니처는 유지)
[ ] 1-2: build_single_user_profile() 추가 (UserProfileVectors 인스턴스 반환)
[ ] 1-3: xai.py에 build_recommendation_explanation() 배치 헬퍼 추가
[ ] 1-4: ML/serving/main.py 작성 (4개 엔드포인트) + ML/pyproject.toml에 fastapi/uvicorn/httpx 추가
[ ] 1-5: ML/serving/Dockerfile 작성
[ ] 1-6: 로컬 단독 실행 확인 (health + recommend 응답에 hook_line/matched_trait/explanation 포함 확인)
```

---

### STEP 2 — 백엔드 수정

> **정정**: 실제 백엔드 패키지 루트는 `backend/app/`이다(`backend/routers/`, `backend/crud/`, `backend/core/`는 존재하지 않음). CRUD 전용 디렉터리가 없고 `backend/app/services/`가 그 역할을 한다. 전용 `/onboarding` 엔드포인트도 없다 — 온보딩과 마이페이지 취향 재설정이 `PATCH /api/users/me/profile`(`backend/app/routers/users.py`) 하나를 공유한다. `GET /api/recommendations`는 이미 `RecommendationOut(bookId, hookLine, matchedTrait, explanation)` 스키마로 응답 중이라 스키마는 그대로 두고 내부 구현만 바꾼다. 문서 원안의 `/explain` 지연 호출 엔드포인트는 만들지 않는다 — (사용자 결정) 설명은 `/api/recommendations` 응답에 이미 함께 실려 온다(STEP 1-4 참고).

**2-1. 환경변수 + `Settings` 추가**

```bash
# .env, .env.example (로컬)
ML_SERVER_URL=http://localhost:8001
ADMIN_SECRET=change-me   # ML 서버와 동일한 값
```

```python
# backend/app/config.py
class Settings(BaseSettings):
    ...
    ml_server_url: str = "http://localhost:8001"
    admin_secret: str = "change-me"
```

**2-2. `backend/app/services/book_service.py`에 isbn 리스트 조회 추가**

```python
def get_books_by_isbn(db: Session, isbn_list: list[str]) -> list[Book]:
    return db.query(Book).filter(Book.isbn.in_(isbn_list)).all()
```

**2-3. `backend/app/routers/recommendations.py` 수정 — 더미 로직을 ML 호출로 교체**

`RecommendationOut` 스키마(`backend/app/schemas/recommendation.py`)는 그대로 두고, `get_recommendations()` 내부만 랜덤 샘플링에서 ML 서버 호출로 바꾼다.

```python
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.security import get_current_user
from app.services import book_service
from app.schemas.recommendation import RecommendationOut

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.get("/recommendations", response_model=list[RecommendationOut])
async def get_recommendations(
    n: int = Query(default=10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{settings.ml_server_url}/recommend",
                json={"user_id": str(current_user.id), "k": n},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="ML 서버 연결 실패")

    recommended = resp.json()   # [{book_id, hook_line, matched_trait, explanation}, ...]
    if not recommended:
        return []   # 온보딩 미완료 등으로 ML 프로필이 없는 유저 — 빈 추천 목록 반환

    isbn_list = [item["book_id"] for item in recommended]
    books_by_isbn = {b.isbn: b for b in book_service.get_books_by_isbn(db, isbn_list)}

    return [
        RecommendationOut(
            bookId=item["book_id"],
            hookLine=item["hook_line"],
            matchedTrait=item["matched_trait"],
            explanation=item["explanation"],
        )
        for item in recommended
        if item["book_id"] in books_by_isbn   # ML이 반환한 isbn이 DB에 없으면(시드 불일치 등) 건너뜀
    ]
```

`GET /api/reviews/{review_id}/similar-books`는 이번 STEP의 대상이 아니다(정합성 점검 F 참고) — 랜덤 더미 그대로 둔다.

**2-4. `PATCH /api/users/me/profile`에 ML 프로필 등록 추가**

(사용자 결정) 이 엔드포인트가 온보딩·마이페이지 취향 재설정을 모두 처리하므로, 호출될 때마다 **DB에 upsert된 병합 후 전체 프로필**을 ML `/profile/build`로 다시 보낸다. 부분 PATCH(예: `avoidedTraits`만 보냄)라도 DB에서 최종 저장된 `preferred_emotions`/`avoided_traits` 전체를 읽어 보내야 한다 — PATCH 페이로드만 그대로 전달하면 요청에 없는 필드가 빈 배열로 ML에 전달되어 기존 선호 신호가 사라진다.

```python
# backend/app/routers/users.py
@router.patch("/me/profile", response_model=UserProfileOut)
async def update_my_profile(
    payload: UserProfileUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = upsert_user_profile(db, current_user.id, payload)   # 기존 로직 — DB upsert

    # 추가: ML 서버에 병합된 전체 프로필 등록 (실패해도 PATCH 자체는 성공 처리)
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.ml_server_url}/profile/build",
                json={
                    "user_id": str(current_user.id),
                    "preferred_emotions": profile.preferred_emotions,
                    "avoided_traits": profile.avoided_traits,
                },
                timeout=10.0,
            )
    except httpx.HTTPError:
        pass   # 로그만 남기고 계속 — ML 프로필 등록 실패가 취향 저장 자체를 막지 않음

    return profile
```

**2-5. `backend/app/routers/events.py` 신규 작성**

프론트에서 impression/click 이벤트를 기록하는 엔드포인트.

> **정정**: `book_id`는 정수가 아니라 `books.isbn`(문자열)이다. `user_id`는 `get_current_user`가 이미 `UUID`로 준다.

```python
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_user
from app.models.recommendation_event import RecommendationEvent

router = APIRouter(prefix="/api/events", tags=["events"])


class EventRequest(BaseModel):
    book_id: str            # books.isbn
    event_type: str         # impression / click / like / review
    source: str              # home / book_detail / review_detail
    rank: int | None = None  # impression일 때만 사용


@router.post("")
def log_event(
    req: EventRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.add(RecommendationEvent(
        user_id=current_user.id,
        book_id=req.book_id,
        event_type=req.event_type,
        source=req.source,
        rank=req.rank,
    ))
    db.commit()
    return {"status": "ok"}
```

> `backend/app/main.py`에 `app.include_router(events.router)` 추가 필요(다른 라우터와 동일 패턴).

**2-6. 프론트엔드 이벤트 로깅 추가 (신규 기능 — 기존에 전혀 없음)**

> **정정**: `CLAUDE.md`가 "컴포넌트는 데이터를 직접 만들지 않는다 — 항상 `/hooks`를 통해서만 받는다"를 명시하므로, 컴포넌트에서 `fetch()`를 직접 호출하는 원안 대신 다른 훅들과 동일하게 `app/src/lib/apiClient.ts`의 `apiFetch`를 감싼 신규 훅을 만든다.

```typescript
// app/src/hooks/useLogEvent.ts
import { apiFetch } from '../lib/apiClient';

export interface RecommendationEventInput {
  bookId: string;
  eventType: 'impression' | 'click' | 'like' | 'review';
  source: 'home' | 'book_detail' | 'review_detail';
  rank?: number;
}

export function useLogEvent() {
  const logEvent = (input: RecommendationEventInput) => {
    apiFetch('/api/events', {
      method: 'POST',
      body: JSON.stringify({
        book_id: input.bookId,
        event_type: input.eventType,
        source: input.source,
        rank: input.rank,
      }),
    }).catch(() => {});   // 로깅 실패가 화면 동작을 막지 않음
  };
  return { logEvent };
}
```

```tsx
// app/src/pages/HomePage.tsx — useRecommendations() 결과 렌더링 시 (impression)
const { logEvent } = useLogEvent();

useEffect(() => {
  recommendations.forEach((rec, index) => {
    logEvent({ bookId: rec.bookId, eventType: 'impression', source: 'home', rank: index + 1 });
  });
}, [recommendations]);

// 추천 도서 클릭 시 (click)
const handleBookClick = (book: Book, rank: number) => {
  logEvent({ bookId: book.id, eventType: 'click', source: 'home', rank });
  onSelectBook(book.id);
};
```

**체크리스트**
```
[ ] 2-1: Settings에 ml_server_url/admin_secret 추가 + .env, .env.example 갱신
[ ] 2-2: book_service.py에 get_books_by_isbn() 추가
[ ] 2-3: recommendations.py의 GET /api/recommendations를 ML 호출로 교체 (RecommendationOut 스키마 유지)
[ ] 2-4: PATCH /api/users/me/profile에서 병합된 전체 프로필을 매번 /profile/build로 전송
[ ] 2-5: events.py 신규 작성 (book_id: str) + main.py에 라우터 등록
[ ] 2-6: 프론트 useLogEvent() 훅 신규 작성 + HomePage에서 impression/click 호출
```

---

### STEP 3 — 로컬 통합 테스트 (docker-compose)

**3-1. `docker-compose.yml` ml 서비스 추가**

```yaml
services:
  db:
    image: postgres:16
    # 기존 설정 유지

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - ML_SERVER_URL=http://ml:8001
      - ADMIN_SECRET=change-me
    depends_on:
      - db
      - ml

  ml:
    build:
      context: .
      dockerfile: ML/serving/Dockerfile
    ports:
      - "8001:8001"
    environment:
      - ADMIN_SECRET=change-me
    volumes:
      - ./ML:/app/ML
      - ./data/processed:/app/data/processed
```

**3-2. 통합 테스트 확인 항목**

```bash
docker-compose up

# 1. ML 서버 카탈로그 빌드 완료 확인 (로그에서 확인)
# 2. 헬스체크
curl localhost:8001/health
# → {"catalog_loaded": true, "profiles_loaded": true}

# 3. 온보딩 → 추천 흐름
# (1) 회원가입 + 로그인
# (2) 온보딩 완료 → ML 서버 /profile/build 호출 확인
# (3) GET /api/recommendations → 실제 책 데이터 반환 확인

# 4. 이벤트 로깅
curl -X POST localhost:8000/api/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"book_id": 1, "event_type": "click", "source": "home", "rank": 1}'
# DB recommendation_events 테이블에 행 추가 확인
```

**체크리스트**
```
[ ] 3-1: docker-compose.yml ml 서비스 추가
[ ] 3-2: docker-compose up 후 전체 흐름 확인
         ├── health 정상
         ├── 온보딩 → 추천 결과 반환
         └── 이벤트 로깅 DB 적재 확인
```

---

### STEP 4 — Docker Hub 이미지 푸시

로컬 통합 테스트 통과 후 K8s 배포 전에 이미지를 푸시.

```bash
# Docker Hub 로그인
docker login

# 이미지 빌드 + 푸시
docker build -t <dockerhub-id>/literec-backend:latest ./backend
docker build -t <dockerhub-id>/literec-ml:latest -f ML/serving/Dockerfile .
docker build -t <dockerhub-id>/literec-frontend:latest ./app

docker push <dockerhub-id>/literec-backend:latest
docker push <dockerhub-id>/literec-ml:latest
docker push <dockerhub-id>/literec-frontend:latest
```

**체크리스트**
```
[ ] 4-1: Docker Hub 계정 생성 (없으면)
[ ] 4-2: 3개 이미지 빌드 + 푸시 완료
```

---

### STEP 5 — AWS EC2 + k3s 구성

**5-1. EC2 인스턴스 생성**

| 항목 | 설정 |
|---|---|
| 인스턴스 타입 | t3.medium (2vCPU, 4GB) |
| OS | Ubuntu 22.04 LTS |
| 스토리지 | EBS gp3 30GB |
| Security Group | 22(SSH), 80(HTTP), 443(HTTPS), 6443(k3s API — 내 IP만) |

**5-2. k3s 설치**

```bash
# EC2에 SSH 접속 후
curl -sfL https://get.k3s.io | sh -

# 설치 확인
kubectl get nodes
# NAME     STATUS   ROLES                  AGE
# ip-...   Ready    control-plane,master   1m

# 로컬 kubectl 연결용 kubeconfig 복사
cat /etc/rancher/k3s/k3s.yaml
# → GitHub Secrets의 KUBECONFIG에 등록
```

**5-3. 네임스페이스 생성**

```bash
kubectl create namespace backend
kubectl create namespace ml
kubectl create namespace data
kubectl create namespace monitoring
```

**체크리스트**
```
[ ] 5-1: EC2 인스턴스 생성 + Security Group 설정
[ ] 5-2: k3s 설치 + kubectl 정상 동작 확인
[ ] 5-3: 네임스페이스 4개 생성
```

---

### STEP 6 — K8s 매니페스트 작성 + 수동 배포

배포 순서: PostgreSQL → Backend → ML 서버 → Frontend → Ingress

**6-1. `infra/k8s/data/postgres.yaml`**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: data
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    spec:
      containers:
      - name: postgres
        image: postgres:16
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 5Gi
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: data
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
```

**6-2. `infra/k8s/backend/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: backend
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: backend
        image: <dockerhub-id>/literec-backend:latest
        env:
        - name: DATABASE_URL
          value: "postgresql://user:pass@postgres.data.svc.cluster.local:5432/literec"
        - name: ML_SERVER_URL
          value: "http://ml-server.ml.svc.cluster.local:8001"
        - name: ADMIN_SECRET
          valueFrom:
            secretKeyRef:
              name: admin-secret
              key: value
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: backend
spec:
  selector:
    app: backend
  ports:
  - port: 8000
```

**6-3. `infra/k8s/ml/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-server
  namespace: ml
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: ml-server
        image: <dockerhub-id>/literec-ml:latest
        env:
        - name: ADMIN_SECRET
          valueFrom:
            secretKeyRef:
              name: admin-secret
              key: value
        ports:
        - containerPort: 8001
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 90    # build_catalog() 완료 대기 — 실측 후 조정
          periodSeconds: 10
          failureThreshold: 6
---
apiVersion: v1
kind: Service
metadata:
  name: ml-server
  namespace: ml
spec:
  selector:
    app: ml-server
  ports:
  - port: 8001
```

**6-4. `infra/k8s/backend/frontend-deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: backend
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: frontend
        image: <dockerhub-id>/literec-frontend:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: backend
spec:
  selector:
    app: frontend
  ports:
  - port: 80
```

**6-5. `infra/k8s/ingress.yaml`**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: literec-ingress
  namespace: backend
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
  - http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
```

> `/admin/*` 경로는 Ingress에서 노출하지 않음. ML 서버 `/admin/rebuild-catalog`는  
> ClusterIP 내부에서만 접근 (CronJob Pod → ml-server Service 직접 호출).

**6-6. 수동 배포 + 확인**

```bash
kubectl apply -f infra/k8s/data/
kubectl apply -f infra/k8s/backend/
kubectl apply -f infra/k8s/ml/
kubectl apply -f infra/k8s/ingress.yaml

# 각 Pod 상태 확인
kubectl get pods -A

# 시드 데이터 Job 실행 (마이그레이션 + 88권 + 440 리뷰 적재)
kubectl apply -f infra/k8s/jobs/seed-data.yaml

# EC2 Public IP로 브라우저 접근 확인
```

**체크리스트**
```
[ ] 6-1: postgres.yaml 작성 + 배포 확인
[ ] 6-2: backend deployment.yaml 작성 + 배포 확인
[ ] 6-3: ml deployment.yaml 작성 + 배포 확인
         (readinessProbe 통과까지 대기)
[ ] 6-4: frontend deployment.yaml 작성 + 배포 확인
[ ] 6-5: ingress.yaml 작성 + 외부 접근 확인
[ ] 6-6: seed-data Job 실행 + DB 적재 확인
[ ] 6-7: EC2 IP로 추천 API 엔드투엔드 확인
```

---

### STEP 7 — GitHub Actions CI/CD

**7-1. GitHub Secrets 등록**

| Secret | 내용 |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub 아이디 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |
| `KUBECONFIG` | EC2의 `/etc/rancher/k3s/k3s.yaml` 내용 (server URL을 EC2 Public IP로 교체) |

**7-2. `.github/workflows/deploy.yml` 작성**

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Login to Docker Hub
        run: echo ${{ secrets.DOCKERHUB_TOKEN }} | docker login -u ${{ secrets.DOCKERHUB_USERNAME }} --password-stdin
      - name: Build & Push backend
        run: |
          docker build -t ${{ secrets.DOCKERHUB_USERNAME }}/literec-backend:latest ./backend
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/literec-backend:latest
      - name: Deploy to K8s
        run: |
          echo "${{ secrets.KUBECONFIG }}" > kubeconfig.yaml
          KUBECONFIG=kubeconfig.yaml kubectl rollout restart deployment/backend -n backend

  deploy-ml:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Login to Docker Hub
        run: echo ${{ secrets.DOCKERHUB_TOKEN }} | docker login -u ${{ secrets.DOCKERHUB_USERNAME }} --password-stdin
      - name: Build & Push ml
        run: |
          docker build -t ${{ secrets.DOCKERHUB_USERNAME }}/literec-ml:latest -f ML/serving/Dockerfile .
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/literec-ml:latest
      - name: Deploy to K8s
        run: |
          echo "${{ secrets.KUBECONFIG }}" > kubeconfig.yaml
          KUBECONFIG=kubeconfig.yaml kubectl rollout restart deployment/ml-server -n ml

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Login to Docker Hub
        run: echo ${{ secrets.DOCKERHUB_TOKEN }} | docker login -u ${{ secrets.DOCKERHUB_USERNAME }} --password-stdin
      - name: Build & Push frontend
        run: |
          docker build -t ${{ secrets.DOCKERHUB_USERNAME }}/literec-frontend:latest ./app
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/literec-frontend:latest
      - name: Deploy to K8s
        run: |
          echo "${{ secrets.KUBECONFIG }}" > kubeconfig.yaml
          KUBECONFIG=kubeconfig.yaml kubectl rollout restart deployment/frontend -n backend
```

**체크리스트**
```
[ ] 7-1: GitHub Secrets 3개 등록
[ ] 7-2: deploy.yml 작성
[ ] 7-3: main 브랜치에 push → 자동 배포 확인
```

---

### STEP 8 — CronJob (온라인 파이프라인)

**8-1. 일 단위 CronJob — 신규 리뷰 임베딩 + Buffer 적재**

```
매일 새벽 2시 실행
  1. DB에서 is_processed=FALSE 인 리뷰 조회
  2. 리뷰 텍스트 → 5축 정규화 문장 변환
  3. Sentence-Transformer 임베딩
  4. 임베딩 결과를 buffer 파일(또는 임시 테이블)에 적재
  (아직 KMeans 재실행 안 함 — 아이덴티티 벡터 변경 없음)
```

`infra/k8s/cronjobs/daily-embed.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-embed
  namespace: ml
spec:
  schedule: "0 2 * * *"   # 매일 새벽 2시
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: embed-job
            image: <dockerhub-id>/literec-ml:latest
            command: ["uv", "run", "python", "-m", "ML.pipeline.cronjobs.daily_embed"]
            env:
            - name: DATABASE_URL
              value: "postgresql://...@postgres.data.svc.cluster.local:5432/literec"
          restartPolicy: OnFailure
```

`ML/pipeline/cronjobs/daily_embed.py`:

> **정정**: `backend.db`/`backend.models.review`가 아니라 `app.db`(`SessionLocal`)/`app.models.review`다(실행 시 `PYTHONPATH`에 `backend/`를 잡아줘야 함). `get_db_session()`이라는 컨텍스트매니저는 없다 — `SessionLocal()`을 직접 열고 닫는다.
>
> **더 근본적인 미해결 문제**: `to_sentence()`(`ML/pipeline/embedding.py`)는 `정서_경험`/`좋았던_요소`/`별로였던_요소`/`소재_및_주제`/`독서_경험_맥락` 5축 딕셔너리를 입력으로 기대한다. 하지만 백엔드 `reviews` 테이블에는 이 5축 컬럼이 없다 — `emotion_tags`/`liked_points`/`disliked_points`(평문 문자열 배열)뿐이고, `structured_axes` 같은 컬럼 자체가 존재하지 않는다.
> **구조화 로직 자체는 이미 있다 — 없는 건 "실사용자 리뷰에 대한 자동 호출 경로"뿐**: `data/src/llm_review/structure_reviews.py`가 5축 구조화를 이미 구현해 두었고(프롬프트는 `data/src/llm_review/prompt_builder.py`의 `build_structure_prompt()`, 호출은 Upstage Solar API), 초기 440건(`data/processed/structured_reviews.jsonl`)이 이걸로 만들어졌다. 다만 이 스크립트는 `uv run python src/llm_review/structure_reviews.py 0 87`처럼 **사람이 CLI로 수동 실행하는 오프라인 배치**로만 짜여 있고, 책 단위(`isbn`별 리뷰 5개 묶음)·이미 처리된 isbn skip 같은 "초기 440건 일괄 처리"에 맞춘 구조다. 실사용자가 게시판에 새로 쓰는 리뷰(`source='user'`)를 같은 5축으로 자동 구조화해서 DB/버퍼에 채우는 경로는 아직 없다. STEP 8 착수 전에 `build_structure_prompt()` + Upstage 호출 부분을 "리뷰 1건 단위" 함수로 뽑아 재사용하면서, (a) 리뷰 작성 시점에 실시간으로 돌릴지, (b) 이 CronJob이 매일 신규 리뷰(`is_processed=FALSE`)에 대해 배치로 호출할지부터 정해야 한다. 아래 코드는 "5축 데이터가 이미 있다고 가정"한 자리표시자다.

```python
"""일 단위: is_processed=FALSE 리뷰 임베딩 → buffer 적재
※ reviews 테이블에 5축 구조화 컬럼이 아직 없어 to_sentence() 입력을 만들 방법이 없다 —
   착수 전 위 "더 근본적인 미해결 문제" 참고."""
from ML.pipeline.embedding import to_sentence, embed
from app.db import SessionLocal
from app.models.review import Review
import numpy as np, os

BUFFER_PATH = os.getenv("BUFFER_PATH", "data/processed/embedding_buffer.npy")

def run():
    db = SessionLocal()
    try:
        new_reviews = db.query(Review).filter(Review.is_processed == False).all()
    finally:
        db.close()

    if not new_reviews:
        print("신규 리뷰 없음, 종료")
        return

    texts = [to_sentence(r.structured_axes) for r in new_reviews]  # TODO: structured_axes 소스 확정 필요
    embeddings = embed(texts)

    # 기존 buffer에 append
    if os.path.exists(BUFFER_PATH):
        existing = np.load(BUFFER_PATH, allow_pickle=True)
        combined = np.vstack([existing, embeddings])
    else:
        combined = embeddings

    np.save(BUFFER_PATH, combined)
    print(f"{len(new_reviews)}건 임베딩 buffer 적재 완료")
    # ※ is_processed 갱신은 주 단위 CronJob에서 처리

if __name__ == "__main__":
    run()
```

**8-2. 주 단위 CronJob — KMeans 재실행 + 카탈로그 갱신**

```
매주 일요일 새벽 3시 실행
  1. buffer 임베딩 + 기존 임베딩 합산
  2. KMeans(k=30) 재실행
  3. 책 아이덴티티 벡터 재계산
  4. POST /admin/rebuild-catalog → ML 서버 캐시 갱신
  5. DB reviews.is_processed = TRUE 일괄 갱신
```

`infra/k8s/cronjobs/weekly-rebuild.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: weekly-rebuild
  namespace: ml
spec:
  schedule: "0 3 * * 0"   # 매주 일요일 새벽 3시
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: rebuild-job
            image: <dockerhub-id>/literec-ml:latest
            command: ["uv", "run", "python", "-m", "ML.pipeline.cronjobs.weekly_rebuild"]
            env:
            - name: DATABASE_URL
              value: "postgresql://...@postgres.data.svc.cluster.local:5432/literec"
            - name: ML_SERVER_URL
              value: "http://ml-server.ml.svc.cluster.local:8001"
            - name: ADMIN_SECRET
              valueFrom:
                secretKeyRef:
                  name: admin-secret
                  key: value
          restartPolicy: OnFailure
```

`ML/pipeline/cronjobs/weekly_rebuild.py`:

> **정정**: `build_catalog(force_rebuild=True)`는 이 스크립트 자신의 프로세스(=별도 K8s Job Pod) 메모리에서만 재계산될 뿐, 실제로 트래픽을 받는 ML 서버(`ml-server` Deployment)의 캐시에는 아무 영향이 없다 — 두 프로세스가 메모리를 공유하지 않는다. "재계산"은 `POST /admin/rebuild-catalog` 호출 한 번으로 충분하다(그 엔드포인트가 서버 프로세스 안에서 `ensure_catalog_loaded(force_rebuild=True)`를 실행한다, STEP 1-4 참고). 이 스크립트에서 로컬로 다시 계산하는 코드는 삭제한다. DB import 경로도 `app.db`/`app.models.review`로 수정.

```python
"""주 단위: /admin/rebuild-catalog 호출로 ML 서버 캐시 갱신 → is_processed 갱신"""
import requests, os

ML_URL = os.getenv("ML_SERVER_URL", "http://localhost:8001")
SECRET = os.getenv("ADMIN_SECRET", "change-me")

def run():
    # 1. ML 서버에 캐시 재계산 요청 (서버 프로세스 안에서 ensure_catalog_loaded(force_rebuild=True) 실행)
    resp = requests.post(
        f"{ML_URL}/admin/rebuild-catalog",
        headers={"x-admin-secret": SECRET},
        timeout=120
    )
    resp.raise_for_status()
    print("카탈로그 갱신 완료")

    # 2. 처리된 리뷰 is_processed=TRUE 갱신
    from app.db import SessionLocal
    from app.models.review import Review
    db = SessionLocal()
    try:
        db.query(Review).filter(Review.is_processed == False)\
            .update({"is_processed": True})
        db.commit()
    finally:
        db.close()
    print("is_processed 갱신 완료")

if __name__ == "__main__":
    run()
```

**8-3. CTR 집계 CronJob — Grafana용 메트릭**

```
매일 새벽 1시 실행
  recommendation_events 테이블에서 전일 데이터 집계
  → CTR(click/impression), 전환율(review/click) 계산
  → 집계 결과를 별도 테이블 또는 Prometheus push gateway에 전송
```

집계 SQL 예시:

```sql
SELECT
  DATE(created_at)                                    AS date,
  source,
  COUNT(*) FILTER (WHERE event_type = 'impression')   AS impressions,
  COUNT(*) FILTER (WHERE event_type = 'click')        AS clicks,
  COUNT(*) FILTER (WHERE event_type = 'review')       AS reviews,
  ROUND(
    COUNT(*) FILTER (WHERE event_type = 'click')::numeric
    / NULLIF(COUNT(*) FILTER (WHERE event_type = 'impression'), 0), 4
  )                                                   AS ctr
FROM recommendation_events
WHERE created_at >= NOW() - INTERVAL '1 day'
GROUP BY DATE(created_at), source
ORDER BY date DESC;
```

**체크리스트**
```
[ ] 8-1: ML/pipeline/cronjobs/daily_embed.py 작성
[ ] 8-1: infra/k8s/cronjobs/daily-embed.yaml 작성 + 배포
[ ] 8-2: ML/pipeline/cronjobs/weekly_rebuild.py 작성
[ ] 8-2: infra/k8s/cronjobs/weekly-rebuild.yaml 작성 + 배포
[ ] 8-2: kubectl create job --from=cronjob/weekly-rebuild 으로 수동 1회 실행 테스트
[ ] 8-3: CTR 집계 CronJob 작성 (여유 있으면)
```

---

### STEP 9 — 모니터링 (Prometheus + Grafana)

```bash
# Helm으로 설치
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring

# Grafana 접근
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
# localhost:3000 접속 (admin/prom-operator)
```

**Grafana 대시보드 구성 항목**:
- 추론 레이턴시 (`/api/recommendations` 응답시간)
- CTR 일별 추이 (source별)
- 리뷰 전환율 (click → review)
- ML 서버 카탈로그 마지막 갱신 시각
- K8s Pod CPU/메모리 사용량

**체크리스트**
```
[ ] 9-1: Helm으로 Prometheus + Grafana 설치
[ ] 9-2: Grafana 접속 확인
[ ] 9-3: CTR 대시보드 패널 구성
[ ] 9-4: Locust로 부하 테스트 실행 + 레이턴시 그래프 확인
```

---

## 주의사항

**ML 서버 시작 시간**  
`lifespan()`의 `ensure_catalog_loaded()`(리뷰 임베딩 440건 + KMeans)가 완료되기 전에 트래픽이 들어오면 오류 발생.  
`readinessProbe.initialDelaySeconds`를 실제 소요 시간보다 넉넉하게 설정 필요.  
EC2에서 실제 시간 측정 후 조정.

**데이터 경로 하드코딩**  
`aspect_based_model.py`의 jsonl 경로(`STRUCTURED_REVIEWS_PATH` 등)가 `__file__` 기준 상대 경로로 고정되어 있어 Docker 이미지 내 경로와 불일치 발생 가능.  
환경변수(`DATA_DIR`)로 교체 권장.

**user_id 타입 통일**  
`recommend(user_id: str)`에 전달하는 값과 `eval_users.json`의 `userId`(한글 이름 문자열, 팀원 4명 오프라인 평가용) 형식이 일치해야 함.  
백엔드 DB의 `users.id`는 `UUID`이므로 `str(current_user.id)`로 변환해서 전달. 실제 가입 유저는 `eval_users.json`에 없으므로, 온보딩(`PATCH /api/users/me/profile`, STEP 2-4)에서 `/profile/build`를 호출하기 전까지는 `recommend()`가 빈 리스트를 반환하는 게 정상 동작.

**ADMIN_SECRET 노출 방지**  
`/admin/rebuild-catalog`는 Ingress에서 외부 노출 안 됨.  
K8s Secret으로 관리하고 CronJob Pod에만 환경변수로 주입.

**is_processed / created_at 초기값**  
기존 LLM 생성 리뷰 440건의 `is_processed=TRUE`, `created_at=2026-07-26 23:28:11+09`(커밋 시각) 설정은 마이그레이션이 아니라 **`backend/scripts/seed_data.py` 자체에서 명시적으로** 처리한다(STEP 0-1b 참고) — 이미 잘못 적재된 행이 있다면 그 섹션의 backfill SQL을 1회 실행.

---

## 정합성 점검 결과 (2026-08-12)

STEP 0부터 순서대로 구현에 착수하기 전, 이 문서(작성 시점 기준 계획)와 실제 코드(백엔드 모델/라우터, `ML/pipeline/*.py`, 프론트엔드 `app/src/*`)를 대조해서 발견한 불일치를 정리한다. `report/UI_QA_FEEDBACK.md`와 같은 방식(재현/원인/상태)으로 기록했다. 이번 점검에서는 문서만 고쳤고 실제 코드는 건드리지 않았다 — 아래 각 항목의 실제 구현은 해당 STEP에서 진행한다.

### A. `reviews.created_at`은 이미 있음 — "없음" 전제가 틀렸음

**원래 전제**: STEP 0이 `created_at`/`is_processed` 두 컬럼을 함께 새로 추가한다고 되어 있었음.
**실제**: `created_at`은 `0001_initial_schema` 마이그레이션에 이미 있다. 없는 건 `is_processed` 하나뿐.
**진짜 문제**: 컬럼이 아니라 값 — `seed_data.py`가 440건의 LLM 리뷰를 넣을 때 `created_at`을 지정하지 않아 전부 "시드 스크립트 실행 시각"으로 찍힌다.
**상태**: 문서 정정 완료(STEP 0-1, 0-1b). `llm_reviews.jsonl` 최초 커밋 시각(`1c96df5`, 2026-07-26 23:28:11+09)으로 명시 설정하도록 시드 스크립트 수정 지시를 추가. 실제 코드 수정은 STEP 0 구현 시 진행.

### B. 프론트엔드는 이미 리뷰 작성일 · XAI 설명을 표시하고 있음

**요청 배경**: "현재 프론트에는 리뷰 생성 일자를 표기하는 부분이 없다"는 전제로 표기 자리를 만들어달라는 요청이 있었음.
**실제 확인**: `Review.createdAt`(`UI_DESIGN_SPEC.md` 5.1)은 이미 `app/src/components/review/ReviewCard.tsx`와 `app/src/pages/ReviewDetailPage.tsx` 양쪽에서 `new Date(review.createdAt).toLocaleDateString('ko-KR')`로 렌더링되고 있다. `Recommendation.explanation`도 `XAINote` 컴포넌트로 홈 화면에 이미 렌더링 중이다.
**결론**: 프론트엔드에 새로 만들 UI 자리는 없다. A의 시드 스크립트 수정만으로 이미 있는 화면에 올바른 날짜가 나온다. 이 문서에는 프론트 변경 항목을 추가하지 않았다.
**참고**: 반대로 추천 노출/클릭 이벤트 로깅은 프론트에 전혀 없어(그 어떤 훅/컴포넌트에도 `fetch`/이벤트 호출 없음) STEP 2-6에서 신규로 만든다 — 이건 원래 계획이 맞았음.

### C. `recommendation_events` FK 타입이 실제 스키마와 다름

**원래 코드**: `user_id`/`book_id` 둘 다 `sa.Integer()` FK.
**실제 스키마**: `users.id`는 `UUID`, `books`는 정수 `id`가 없고 `isbn`(문자열)이 PK — `books.id` 자체가 존재하지 않는다.
**영향**: 원안대로 마이그레이션을 실행하면 FK 대상 컬럼이 없어 즉시 실패한다.
**상태**: STEP 0-2/0-3에서 `user_id UUID FK→users.id`, `book_id String FK→books.isbn`으로 정정.

### D. ML 서빙(STEP 1) 예시 코드가 실제 `aspect_based_model.py`/`xai.py`와 맞지 않음

**발견한 문제 4가지**(자세한 설명은 STEP 1 도입부 참고):
1. `build_catalog()`에 `force_rebuild` 파라미터가 없음 → 원안대로면 `TypeError`.
2. `_catalog_cache`/`_user_profiles_cache`가 `recommend()` 내부 `global`로만 채워짐 → 원안의 `lifespan()`은 캐시를 채우지 못하고, `from ... import _catalog_cache`는 `None` 스냅샷을 영구 고정 → `/health`가 항상 `false`.
3. `build_single_user_profile()`이 없고, 캐시에 넣어야 할 건 튜플이 아니라 `UserProfileVectors` 인스턴스.
4. `explain_recommendation()`의 실제 시그니처(`user_vector, book_id, identity, result, review_embeddings, reviews_by_id`)가 원안(2-인자)과 완전히 다름 — 지금 캐시 구조로는 필요한 인자를 만들 수 없음.
**상태**: STEP 1을 `CatalogBundle` + `ensure_catalog_loaded()`/`ensure_profiles_loaded()` 접근자 구조로 재작성. (사용자 결정) `/recommend`가 스코어링과 동시에 상위 K권의 설명까지 배치로 반환하도록 `xai.build_recommendation_explanation()` 신규 헬퍼 추가.

### E. 백엔드(STEP 2) 예시의 경로/엔드포인트가 실제 코드와 다름

**원래 코드**: `backend/routers/recommendations.py`, `backend/crud/books.py`, `backend/core/config.py`, 전용 `/onboarding` 엔드포인트.
**실제**: `backend/app/routers/recommendations.py`, CRUD 전용 디렉터리 없음(`backend/app/services/`), `backend/app/config.py`, `/onboarding` 없이 `PATCH /api/users/me/profile`이 온보딩·마이페이지 재설정 겸용.
**추가 발견**: `httpx`가 `dev` 의존성 그룹에만 있어 런타임 코드에서 그대로 쓰면 프로덕션 빌드에서 `ImportError`. `GET /api/recommendations`는 이미 `RecommendationOut` 스키마로 응답 중이라 스키마는 유지, 내부만 교체하면 됨.
**결정 필요했던 사항 (사용자 확인 완료)**:
- `PATCH /api/users/me/profile`은 호출될 때마다(온보딩이든 마이페이지 재설정이든) DB에 upsert된 **병합된 전체 프로필**을 매번 `/profile/build`로 재전송한다. `DESIGN.md`의 "온보딩 1회 생성 후 고정" 전제와는 다르지만, 마이페이지 취향 재설정 기능이 추천에 실제로 반영되게 하려는 선택.
- 추천 카드의 XAI 설명(`hookLine`/`matchedTrait`/`explanation`)은 백엔드가 K권마다 ML `/explain`을 순차 호출하는 대신, ML `/recommend`가 배치로 한 번에 반환한다(원안의 지연 호출 `/explain` 엔드포인트는 만들지 않음).
**상태**: STEP 2 전체 재작성 완료.

### F. 범위 밖으로 확인/기록만 해 둔 항목

- **`GET /api/reviews/{review_id}/similar-books`**(리뷰 상세 "유사 리뷰 기반 책 추천"): `ML_RECOMMENDATION_PIPELINE.md`의 `recommend()` 파이프라인과 무관한 별도 기능이고, 어느 기준 문서에도 설계가 없다. 계속 랜덤 더미로 남겨두고 이번 정정에는 포함하지 않음.
- **`Book.identityVectors`(레이더 차트) ↔ `book_aspects` 매핑**: `LiteRec_Backend_ClaudeCode_Brief.md` 9.1에 이미 "미확정, 별도 논의 필요"로 기록되어 있고 추천 파이프라인과 무관 — 손대지 않음.
- **STEP 8 온라인 임베딩 파이프라인의 5축 구조화 공백**: 구조화 로직 자체(`data/src/llm_review/structure_reviews.py`의 `build_structure_prompt()` + Upstage Solar API 호출)는 이미 있고 초기 440건이 이걸로 만들어졌지만, 사람이 CLI로 수동 실행하는 오프라인 배치 스크립트일 뿐이다. 실사용자가 게시판에 새로 쓰는 리뷰를 같은 5축으로 **자동** 구조화해서 DB/버퍼에 채우는 경로는 어디에도 없다. STEP 8 착수 전 이 로직을 리뷰 1건 단위로 재사용하는 별도 설계 필요 — 이번 정정에서는 코드 스니펫에 TODO만 남겨둠.
- **`matchedTrait`/`hookLine` 필드의 실제 의미**: `UI_DESIGN_SPEC.md` 5.1 타입에는 있지만 어느 화면에서도 렌더링되지 않는 죽은 필드(확인: `HomePage.tsx`는 `explanation`만 사용). STEP 1-3에서 ML 5축 라벨을 `RADAR_TRAITS` 어휘로 잠정 매핑해 채워 넣었지만, 실제로 화면에 노출하게 되면 매핑을 다시 설계해야 한다.
