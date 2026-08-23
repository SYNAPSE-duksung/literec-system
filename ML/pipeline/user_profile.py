"""Phase 3 — 온보딩 설문(선호/기피)을 문장으로 변환해 유저 취향 프로필 벡터를 만든다.

DESIGN.md 5.Phase 3 참고:
- 온보딩에서 선호(preferredEmotions)와 기피(avoidedTraits) 두 종류를 입력받는다
- 각각 문장으로 변환 후 임베딩 -> 선호 벡터, 기피 벡터 2개 생성
- 생성 후 고정 (좋아요/리뷰 작성으로 실시간 갱신하지 않음)

입력 스키마는 프론트엔드에 이미 정의된 것을 그대로 따른다
(app/src/types/index.ts의 UserProfile, app/src/constants/options.ts의 선택지):
  { userId, preferredEmotions: string[], avoidedTraits: string[], likedBookIds: string[] }
likedBookIds는 프로필 생성에는 쓰이지 않는다 (evaluation.py의 정답 라벨용, DESIGN.md 5.Phase 3 참고).

avoidedTraits는 온보딩에서 0개를 선택해도 완료 가능하므로(느낀 기피 요소가 없을 수 있음),
비어 있으면 기피 벡터를 영벡터로 둔다 - Phase 4의 페널티 항(max_sim(기피벡터, ...))이
자연히 0이 되어 별도 분기 없이 "기피 없음"을 표현한다.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from embedding import DEFAULT_MODEL_NAME, embed

EMBEDDING_DIM = 768


def to_preferred_sentence(preferred_emotions: list[str]) -> str:
    if not preferred_emotions:
        return ""
    return f"선호하는 정서: {', '.join(preferred_emotions)}."


def to_avoided_sentence(avoided_traits: list[str]) -> str:
    if not avoided_traits:
        return ""
    return f"기피하는 요소: {', '.join(avoided_traits)}."


@dataclass
class UserProfileVectors:
    user_id: str
    preferred_vector: np.ndarray  # 정규화된 벡터, 항상 존재
    avoided_vector: np.ndarray  # 기피 항목이 없으면 영벡터
    has_avoided: bool  # 기피 벡터가 실제 임베딩 결과인지(True) 영벡터 폴백인지(False)


def build_user_profiles(
    users: list[dict], model_name: str = DEFAULT_MODEL_NAME
) -> dict[str, UserProfileVectors]:
    """여러 유저의 선호/기피 문장을 한 번에 배치 임베딩해 프로필을 만든다.

    빈 문장(선호/기피 항목이 하나도 없는 경우)은 임베딩 대상에서 빼고 영벡터로
    직접 채운다 - 빈 문자열을 모델에 넣으면 의미 없는 벡터가 나오기 때문.
    """
    preferred_sentences = [to_preferred_sentence(u["preferredEmotions"]) for u in users]
    avoided_sentences = [to_avoided_sentence(u["avoidedTraits"]) for u in users]

    non_empty_texts = [s for s in preferred_sentences + avoided_sentences if s]
    embeddings_by_text: dict[str, np.ndarray] = {}
    if non_empty_texts:
        unique_texts = sorted(set(non_empty_texts))
        vectors = embed(unique_texts, model_name=model_name)
        embeddings_by_text = dict(zip(unique_texts, vectors))

    zero_vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)

    profiles: dict[str, UserProfileVectors] = {}
    for user, pref_sentence, avoid_sentence in zip(users, preferred_sentences, avoided_sentences):
        preferred_vector = (
            embeddings_by_text[pref_sentence] if pref_sentence else zero_vector
        )
        has_avoided = bool(avoid_sentence)
        avoided_vector = embeddings_by_text[avoid_sentence] if has_avoided else zero_vector

        profiles[user["userId"]] = UserProfileVectors(
            user_id=user["userId"],
            preferred_vector=preferred_vector,
            avoided_vector=avoided_vector,
            has_avoided=has_avoided,
        )
    return profiles


def save_user_profiles(path: str | Path, profiles: dict[str, UserProfileVectors]) -> None:
    user_ids = list(profiles.keys())
    np.savez_compressed(
        path,
        user_ids=np.array(user_ids, dtype=object),
        preferred_vectors=np.stack([profiles[u].preferred_vector for u in user_ids]),
        avoided_vectors=np.stack([profiles[u].avoided_vector for u in user_ids]),
        has_avoided=np.array([profiles[u].has_avoided for u in user_ids]),
    )


def load_user_profiles(path: str | Path) -> dict[str, UserProfileVectors]:
    data = np.load(path, allow_pickle=True)
    user_ids = data["user_ids"].tolist()
    return {
        uid: UserProfileVectors(
            user_id=uid,
            preferred_vector=data["preferred_vectors"][i],
            avoided_vector=data["avoided_vectors"][i],
            has_avoided=bool(data["has_avoided"][i]),
        )
        for i, uid in enumerate(user_ids)
    }


if __name__ == "__main__":
    mock_path = Path(__file__).parent / "mock_data" / "user_profiles.json"
    with open(mock_path, encoding="utf-8") as f:
        users = json.load(f)

    print(f"입력 유저 수: {len(users)}명\n")
    profiles = build_user_profiles(users)

    for user in users:
        p = profiles[user["userId"]]
        print(f"[{user['userId']}]")
        print(f"  선호: {user['preferredEmotions']}")
        print(f"  기피: {user['avoidedTraits'] or '(없음)'}")
        print(f"  preferred_vector shape={p.preferred_vector.shape}, norm={np.linalg.norm(p.preferred_vector):.4f}")
        print(f"  avoided_vector norm={np.linalg.norm(p.avoided_vector):.4f} (has_avoided={p.has_avoided})")
        print()

    print("=" * 60)
    print("sanity check: 유저 선호/기피 벡터 vs 실제 리뷰 문장 유사도")
    print("=" * 60)
    sample_sentences = [
        ("위로/그리움 계열 리뷰", "정서: 가슴이 먹먹해지고 결말에서 눈물이 핑 돌 만큼 깊은 슬픔과 고독을 느낌. 좋았던 점: 담담한 서술 방식."),
        ("긴장감/추리 계열 리뷰", "정서: 심장이 뛰고 손에 땀이 고이며 긴장감이 오래 남는 여운을 느낌. 좋았던 점: 빠른 전개와 반전."),
        ("장황한 문체 불호 리뷰", "별로였던 요소: 장황하고 늘어지는 문체 때문에 몰입이 계속 끊김. 정서: 지루함과 답답함."),
    ]
    sample_vectors = embed([s for _, s in sample_sentences])

    for user in users:
        p = profiles[user["userId"]]
        print(f"\n[{user['userId']}] 선호={user['preferredEmotions']} 기피={user['avoidedTraits']}")
        for (label, _), vec in zip(sample_sentences, sample_vectors):
            pref_sim = float(np.dot(p.preferred_vector, vec)) if np.linalg.norm(p.preferred_vector) > 0 else 0.0
            avoid_sim = float(np.dot(p.avoided_vector, vec)) if p.has_avoided else 0.0
            print(f"  vs {label}: 선호유사도={pref_sim:.4f}  기피유사도={avoid_sim:.4f}")

    out_path = Path(__file__).parent / "mock_data" / "user_profiles.npz"
    save_user_profiles(out_path, profiles)
    print(f"\n저장 완료: {out_path}")
