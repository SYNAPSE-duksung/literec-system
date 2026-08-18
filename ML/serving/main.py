"""추천 ML 서버 — backend가 이 서비스를 HTTP로 호출한다 (STEP 2-3/2-4 참고).

실행(저장소 루트에서): `uvicorn ML.serving.main:app --port 8001`
ML/pipeline/의 각 모듈이 자기 디렉터리를 sys.path에 꽂아 서로를 flat import하므로,
이 파일은 반드시 저장소 루트가 CWD인 상태에서 패키지 경로(`ML.pipeline....`)로
import해야 한다.
"""

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
    abm.ensure_profiles_loaded()  # eval_users.json (오프라인 평가용 팀원 4명) — 실제 유저는 /profile/build로 추가됨
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict:
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
def get_recommendations(req: RecommendRequest) -> list[RecommendedBookOut]:
    profiles = abm.ensure_profiles_loaded()
    profile = profiles.get(req.user_id)
    if profile is None:
        return []

    bundle = abm.ensure_catalog_loaded()
    book_ids = abm.recommend(req.user_id, k=req.k)

    results = []
    for book_id in book_ids:
        identity = bundle.book_identities.get(book_id)
        if identity is not None:
            explanation = xai.build_recommendation_explanation(
                profile.preferred_vector,
                book_id,
                identity,
                bundle.cluster_result,
                bundle.review_embeddings,
                bundle.reviews_by_id,
            )
        else:
            explanation = {
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
def build_profile(req: BuildProfileRequest) -> dict:
    profile = build_single_user_profile(req.user_id, req.preferred_emotions, req.avoided_traits)
    profiles = abm.ensure_profiles_loaded()
    profiles[req.user_id] = profile  # 같은 dict를 in-place로 갱신 — 재조회 시 바로 반영됨
    return {"status": "ok"}


@app.post("/admin/rebuild-catalog")
def rebuild_catalog(x_admin_secret: str = Header(...)) -> dict:
    """주 단위 CronJob이 KMeans 재실행 후 이 엔드포인트를 호출해 캐시를 갱신.
    ADMIN_SECRET 헤더 불일치 시 403 반환. Ingress에서 /admin/* 경로를 외부에
    노출하지 않아야 한다 (STEP 3 이후 인프라 작업에서 처리)."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    abm.ensure_catalog_loaded(force_rebuild=True)
    return {"status": "ok"}
