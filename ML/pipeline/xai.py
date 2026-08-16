"""Phase 2.5(책 카드) + Phase 5(XAI 설명) — 클러스터(결)에서 대표 문장을 뽑는다.

DESIGN.md 5.Phase 2.5, 5.Phase 5 참고:
- Phase 2.5: 책이 걸쳐 있는 결마다 대표 키워드/문장을 뽑아 "사람이 읽고 판단할 수
  있는 형태"의 책 카드를 만든다 (오프라인 평가 자극용).
- Phase 5: Phase 4에서 어떤 결이 선택됐는지 알아내 그 결의 리뷰들에서 추천 이유를
  뽑는다.
- 두 Phase가 "클러스터에 속한 리뷰들에서 대표 뽑기" 로직을 공유한다.

대표 선정 방법: 클러스터에 속한 이 책의 리뷰들 중 centroid와 코사인 유사도가 가장
높은 리뷰(medoid)를 골라, 그 리뷰의 5축 텍스트를 그대로 대표 내용으로 쓴다. 별도의
키워드 추출(형태소 분석 등)은 하지 않는다 - 한국어는 교착어라 단순 공백 분리로는
조사가 붙은 채 잘려 품질이 떨어지고, 실제 리뷰 문장을 그대로 보여주는 쪽이 위
"사람이 읽고 판단할 수 있는 형태"라는 요구에 더 직접적으로 맞는다.

Phase 5(추천 이유)는 matching.py를 수정하지 않고 만든다 - BookIdentity.cluster_vectors
딕셔너리(label -> centroid)에서 유저 벡터와 가장 유사한 label을 직접 다시 계산하면
되므로, matching.py가 어떤 클러스터가 선택됐는지 별도로 반환하게 확장할 필요가 없다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from clustering import BookIdentity, GlobalClusterResult

AXES = ["정서_경험", "좋았던_요소", "별로였던_요소", "소재_및_주제", "독서_경험_맥락"]


def build_review_embedding_index(
    review_ids: list[str], embeddings: np.ndarray
) -> dict[str, np.ndarray]:
    return {rid: embeddings[i] for i, rid in enumerate(review_ids)}


def find_medoid_review_id(
    member_review_ids: list[str],
    review_embeddings: dict[str, np.ndarray],
    centroid: np.ndarray,
) -> str:
    """centroid와 코사인 유사도가 가장 높은 리뷰(medoid)의 review_id를 반환한다.

    member_review_ids 안에서만 비교하므로(고정된 centroid에 대한 순위 비교) centroid를
    단위 벡터로 정규화하지 않아도 argmax 결과는 동일하다.
    """
    return max(
        member_review_ids,
        key=lambda rid: float(np.dot(review_embeddings[rid], centroid)),
    )


def describe_facet(
    book_id: str,
    cluster_label: int,
    result: GlobalClusterResult,
    review_embeddings: dict[str, np.ndarray],
    reviews_by_id: dict[str, dict],
) -> dict:
    """이 책이 걸쳐 있는 결(cluster_label) 하나를 대표 리뷰(medoid)로 설명한다."""
    member_review_ids = [
        rid
        for rid, bid, label in zip(result.review_ids, result.book_ids, result.labels)
        if bid == book_id and label == cluster_label
    ]
    medoid_id = find_medoid_review_id(
        member_review_ids, review_embeddings, result.centroids[cluster_label]
    )
    medoid_review = reviews_by_id[medoid_id]
    representative_content = {
        axis: medoid_review[axis] for axis in AXES if medoid_review.get(axis)
    }
    return {
        # HDBSCAN의 labels 배열은 np.int64라 int()로 캐스팅해야 JSON 직렬화가 된다.
        "cluster_label": int(cluster_label),
        "member_count": len(member_review_ids),
        "representative_review_id": medoid_id,
        "representative_content": representative_content,
    }


def build_book_card(
    book_id: str,
    identity: BookIdentity,
    result: GlobalClusterResult,
    review_embeddings: dict[str, np.ndarray],
    reviews_by_id: dict[str, dict],
) -> dict:
    """Phase 2.5: 책이 걸쳐 있는 모든 결을 weight 내림차순으로 나열한 카드를 만든다."""
    facets = []
    for label in sorted(
        identity.cluster_vectors, key=lambda l: -identity.cluster_weights[l]
    ):
        facet = describe_facet(book_id, label, result, review_embeddings, reviews_by_id)
        facet["weight"] = identity.cluster_weights[label]
        facets.append(facet)
    return {"book_id": book_id, "facets": facets}


def build_all_book_cards(
    book_identities: dict[str, BookIdentity],
    result: GlobalClusterResult,
    review_embeddings: dict[str, np.ndarray],
    reviews_by_id: dict[str, dict],
) -> list[dict]:
    """카탈로그 전체 책 카드를 만든다. 결이 0개인 책(콜드스타트 대상)은 facets가
    빈 카드로 그대로 포함시킨다 - 평가자가 "이 책은 아직 카드를 못 만들었다"는
    것도 볼 수 있어야 하므로 건너뛰지 않는다.
    """
    cards = []
    for book_id in sorted(book_identities):
        identity = book_identities[book_id]
        if not identity.cluster_vectors:
            cards.append({"book_id": book_id, "facets": []})
            continue
        cards.append(
            build_book_card(book_id, identity, result, review_embeddings, reviews_by_id)
        )
    return cards


def save_book_cards(path: str | Path, cards: list[dict]) -> None:
    """DESIGN.md 5.Phase 2.5가 예시로 든 ML/eval/eval_data/book_cards.json 위치에
    저장할 때 쓴다. 이 함수 자체는 경로를 가리지 않는다."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)


def best_matching_facet_label(
    user_vector: np.ndarray, identity: BookIdentity
) -> int | None:
    """유저 벡터와 가장 유사한 결(cluster_label)을 찾는다 - matching.py의
    max-similarity와 동일한 기준(가장 큰 내적)을 label 단위로 다시 계산한다.
    """
    if not identity.cluster_vectors:
        return None
    return max(
        identity.cluster_vectors,
        key=lambda label: float(np.dot(user_vector, identity.cluster_vectors[label])),
    )


def explain_recommendation(
    user_vector: np.ndarray,
    book_id: str,
    identity: BookIdentity,
    result: GlobalClusterResult,
    review_embeddings: dict[str, np.ndarray],
    reviews_by_id: dict[str, dict],
) -> dict | None:
    """Phase 5: 이 유저에게 이 책을 추천한 근거가 된 결 하나를 설명으로 반환한다.

    콜드스타트 결(coldstart.py가 붙인, 원본 클러스터 라벨이 없는 벡터)이 선택된
    경우는 다루지 않는다 - 이 함수는 Phase 2 결과(BookIdentity.cluster_vectors)만
    보고, matching.py 단계에서 덧붙는 콜드스타트 벡터는 별도로 처리해야 한다.
    """
    label = best_matching_facet_label(user_vector, identity)
    if label is None:
        return None
    facet = describe_facet(book_id, label, result, review_embeddings, reviews_by_id)
    return {"book_id": book_id, **facet}


def format_reason(facet: dict) -> str:
    """대표 내용 dict를 사람이 읽을 짧은 추천 이유 문구로 바꾼다.

    좋았던_요소/정서_경험을 우선으로 하나만 골라 보여준다 - 여러 축을 다 나열하면
    카드/설명이 장황해지므로(별로였던_요소는 추천 이유로 쓰지 않음).
    """
    content = facet["representative_content"]
    for axis in ["좋았던_요소", "정서_경험", "소재_및_주제", "독서_경험_맥락"]:
        if content.get(axis):
            return f"비슷한 독자들이 꼽은 이유: {content[axis]}"
    return "이 책과 잘 맞는 취향의 독자들이 있었어요."


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
    """RecommendationOut(hookLine/matchedTrait/explanation)을 채우는 데 필요한 문구를
    한 번에 만든다. 책에 결이 하나도 없는 순수 콜드스타트 대상은 고정 문구로 대체한다."""
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
        (
            axis
            for axis in ["좋았던_요소", "정서_경험", "소재_및_주제", "독서_경험_맥락"]
            if facet["representative_content"].get(axis)
        ),
        None,
    )
    return {
        "hook_line": reason,
        "matched_trait": AXIS_TO_RADAR_TRAIT.get(matched_axis, "몰입감"),
        "explanation": reason,
    }


if __name__ == "__main__":
    from clustering import global_cluster, compute_book_identities
    from embedding import load_embeddings
    from user_profile import build_user_profiles

    embeddings_path = Path(__file__).parent / "mock_data" / "embeddings.npz"
    book_ids, review_ids, sentences, embeddings = load_embeddings(embeddings_path)
    # 데모용 n_clusters=6: mock 데이터(45개 리뷰)에는 기본값 30이 너무 크다 (clustering.py 참고)
    cluster_result = global_cluster(review_ids, book_ids, embeddings, n_clusters=6)
    book_identities = compute_book_identities(cluster_result)
    review_embeddings = build_review_embedding_index(review_ids, embeddings)

    reviews_path = Path(__file__).parent / "mock_data" / "reviews.json"
    with open(reviews_path, encoding="utf-8") as f:
        book_data = json.load(f)
    title_map = {b["book_id"]: b["title"] for b in book_data["books"]}
    reviews_by_id = {r["review_id"]: r for r in book_data["reviews"]}

    print("=== Phase 2.5: 책 카드 ===")
    cards = build_all_book_cards(book_identities, cluster_result, review_embeddings, reviews_by_id)
    for card in cards:
        book_id = card["book_id"]
        if not card["facets"]:
            print(f"\n[{book_id} {title_map[book_id]}] 결 없음 (콜드스타트 대상)")
            continue
        print(f"\n[{book_id} {title_map[book_id]}]")
        for facet in card["facets"]:
            print(f"  결(cluster {facet['cluster_label']}, weight={facet['weight']:.2f}, {facet['member_count']}건):")
            for axis, value in facet["representative_content"].items():
                print(f"    {axis}: {value}")

    # 실 데이터(88권)용 ML/eval/eval_data/book_cards.json은 아직 저장하지 않는다 -
    # 지금 Phase 2가 HDBSCAN 기준이라 대부분 노이즈로 처리되어(이전 실험 참고)
    # 카드가 비어있는 경우가 많아, 클러스터링 방법이 확정된 뒤에 실 데이터로
    # 다시 생성하는 게 낫다. 대신 mock 데이터로 저장 동작 자체만 검증한다.
    mock_cards_path = Path(__file__).parent / "mock_data" / "book_cards.json"
    save_book_cards(mock_cards_path, cards)
    print(f"\n[저장 완료] {mock_cards_path}")

    print("\n=== Phase 5: 유저별 추천 이유 (b001 데미안 기준) ===")
    users_path = Path(__file__).parent / "mock_data" / "user_profiles.json"
    with open(users_path, encoding="utf-8") as f:
        users = json.load(f)
    profiles = build_user_profiles(users)

    target_book = "b001"
    for user in users:
        profile = profiles[user["userId"]]
        explanation = explain_recommendation(
            profile.preferred_vector, target_book, book_identities[target_book],
            cluster_result, review_embeddings, reviews_by_id,
        )
        reason = format_reason(explanation) if explanation else "(결 없음 - 콜드스타트 대상)"
        print(f"  [{user['userId']}] {reason}")
