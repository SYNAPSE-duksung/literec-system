"""Phase 1 — 5축 구조화 리뷰를 문장으로 변환하고 벡터로 임베딩한다.

DESIGN.md 5.Phase 1 참고:
- to_sentence: 5축 JSON -> 자연어 문장 (5축 필드만 사용, book 메타데이터는 제외)
- embed: 문장 -> 벡터 (jhgan/ko-sroberta-multitask)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = "jhgan/ko-sroberta-multitask"

# DESIGN.md 2절 스키마 순서와 동일하게 유지
_AXIS_LABELS: dict[str, str] = {
    "정서_경험": "정서",
    "좋았던_요소": "좋았던 점",
    "별로였던_요소": "아쉬웠던 점",
    "소재_및_주제": "소재",
    "독서_경험_맥락": "독서 경험",
}

_model_cache: dict[str, SentenceTransformer] = {}


def to_sentence(review: dict) -> str:
    """5축 필드 중 값이 있는 것만 이어 붙여 자연어 문장으로 만든다.

    book 메타데이터(title/author/publisher/summary)는 DESIGN.md 2.1절 규칙에 따라
    사용하지 않는다 — 같은 책의 리뷰끼리 값이 동일해 클러스터를 가르는 신호가
    되지 못하고 노이즈만 늘리기 때문.
    """
    parts = []
    for axis, label in _AXIS_LABELS.items():
        value = review.get(axis)
        if value:
            parts.append(f"{label}: {value}.")
    return " ".join(parts)


def get_model(model_name: str = DEFAULT_MODEL_NAME) -> SentenceTransformer:
    """모델을 최초 1회만 로드하고 이후 호출에서는 캐시를 재사용한다."""
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed(texts: list[str], model_name: str = DEFAULT_MODEL_NAME) -> np.ndarray:
    """문장 리스트를 정규화된 벡터 배열로 변환한다.

    normalize_embeddings=True로 반환해, 이후 Phase 4의 코사인 유사도 계산이
    내적(dot product)만으로 처리되도록 한다.
    """
    model = get_model(model_name)
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def embed_reviews(
    reviews: list[dict], model_name: str = DEFAULT_MODEL_NAME
) -> tuple[list[str], np.ndarray]:
    """리뷰 리스트를 문장으로 변환한 뒤 한 번에 임베딩한다."""
    sentences = [to_sentence(r) for r in reviews]
    embeddings = embed(sentences, model_name=model_name)
    return sentences, embeddings


def save_embeddings(
    path: str | Path,
    book_ids: list[str],
    review_ids: list[str],
    sentences: list[str],
    embeddings: np.ndarray,
) -> None:
    """Phase 2(클러스터링)가 재사용할 수 있도록 임베딩 결과를 압축 저장한다."""
    np.savez_compressed(
        path,
        book_ids=np.array(book_ids, dtype=object),
        review_ids=np.array(review_ids, dtype=object),
        sentences=np.array(sentences, dtype=object),
        embeddings=embeddings,
    )


def load_embeddings(
    path: str | Path,
) -> tuple[list[str], list[str], list[str], np.ndarray]:
    data = np.load(path, allow_pickle=True)
    return (
        data["book_ids"].tolist(),
        data["review_ids"].tolist(),
        data["sentences"].tolist(),
        data["embeddings"],
    )


if __name__ == "__main__":
    mock_path = Path(__file__).parent / "mock_data" / "reviews.json"
    with open(mock_path, encoding="utf-8") as f:
        data = json.load(f)
    reviews = data["reviews"]

    print(f"입력 리뷰 수: {len(reviews)}개")
    sentences, embeddings = embed_reviews(reviews)
    print(f"임베딩 완료: shape={embeddings.shape} (리뷰 수 x 벡터 차원)")

    print("\n문장 변환 예시 (b001 데미안 5건):")
    for r, s in zip(reviews, sentences):
        if r["book_id"] == "b001":
            print(f"  [{r['review_id']} / {r['meta']['label']}] {s}")

    idx = {r["review_id"]: i for i, r in enumerate(reviews)}

    def sim(id_a: str, id_b: str) -> float:
        return float(np.dot(embeddings[idx[id_a]], embeddings[idx[id_b]]))

    print("\n데미안(b001) 호/불호 유사도 sanity check:")
    print(f"  호(r001) vs 호(r002)   = {sim('r001', 'r002'):.4f}")
    print(f"  불호(r003) vs 불호(r004) = {sim('r003', 'r004'):.4f}")
    print(f"  호(r001) vs 불호(r003)  = {sim('r001', 'r003'):.4f}")
    print(f"  호(r002) vs 불호(r004)  = {sim('r002', 'r004'):.4f}")
    print("  (같은 라벨끼리의 유사도가 다른 라벨 간 유사도보다 높으면 기대한 방향)")

    out_path = Path(__file__).parent / "mock_data" / "embeddings.npz"
    book_ids = [r["book_id"] for r in reviews]
    review_ids = [r["review_id"] for r in reviews]
    save_embeddings(out_path, book_ids, review_ids, sentences, embeddings)
    print(f"\n저장 완료: {out_path}")
