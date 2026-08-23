"""STEP8 — 주 단위: /admin/rebuild-catalog 호출로 ML 서버 캐시(카탈로그) 갱신.

문서 원안과 달리 is_processed 갱신은 여기서 하지 않는다 — structure_new_reviews.py가
책 단위 구조화에 성공한 시점에 바로 그 리뷰만 is_processed=TRUE로 표시하므로(정합성
버그 방지, STEP8 계획 참고), 이 스크립트는 review_axes에 쌓인 신규 구조화 리뷰를
실제 클러스터링(추천)에 반영하는 카탈로그 재계산 트리거 역할만 한다.

실행(저장소 루트에서): `uv run --project ML python -m ML.pipeline.cronjobs.weekly_rebuild`
"""

from __future__ import annotations

import os

import httpx

ML_SERVER_URL = os.environ.get("ML_SERVER_URL", "http://localhost:8001")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "change-me")


def run() -> None:
    resp = httpx.post(
        f"{ML_SERVER_URL}/admin/rebuild-catalog",
        headers={"x-admin-secret": ADMIN_SECRET},
        timeout=300.0,  # 리뷰 임베딩 + 클러스터링 재계산 — 인스턴스 사양에 따라 몇 분 걸릴 수 있음
    )
    resp.raise_for_status()
    print("[weekly_rebuild] 카탈로그 갱신 완료")


if __name__ == "__main__":
    run()
