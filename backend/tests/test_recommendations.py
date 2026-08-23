import json

import httpx
import respx

from app.config import settings
from app.models import Book, Review

SIGNUP_PAYLOAD = {"email": "rec@example.com", "password": "password123", "name": "추천"}

ML_RECOMMEND_URL = f"{settings.ml_server_url}/recommend"
ML_SIMILAR_BOOKS_URL = f"{settings.ml_server_url}/similar-books"


def _create_book(db_session, isbn: str) -> Book:
    book = Book(
        isbn=isbn,
        title=f"테스트 도서 {isbn}",
        author="테스트 작가",
        publisher="테스트 출판사",
        cover_url=None,
        synopsis=None,
    )
    db_session.add(book)
    db_session.commit()
    return book


def _login_and_get_token(client) -> str:
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    return res.json()["access_token"]


def _ml_item(isbn: str) -> dict:
    return {
        "book_id": isbn,
        "hook_line": "테스트 훅 라인",
        "matched_trait": "잔잔함",
        "explanation": "테스트 설명",
    }


def _similar_item(isbn: str) -> dict:
    return {"book_id": isbn, "snippet": "테스트 인용문", "reason": "테스트 이유"}


def _create_review_for(db_session, book, **overrides) -> Review:
    fields = {
        "isbn": book.isbn,
        "user_id": None,
        "source": "llm_generated",
        "persona": "테스트 페르소나",
        "content": "테스트 리뷰",
        **overrides,
    }
    review = Review(**fields)
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)
    return review


@respx.mock
def test_recommendations_maps_ml_response_to_recommendation_out(client, db_session):
    token = _login_and_get_token(client)
    isbns = [f"978000000{i:02d}A" for i in range(3)]
    for isbn in isbns:
        _create_book(db_session, isbn)

    respx.post(ML_RECOMMEND_URL).mock(
        return_value=httpx.Response(200, json=[_ml_item(isbn) for isbn in isbns])
    )

    res = client.get(
        "/api/recommendations", params={"n": 3}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    for item in body:
        assert item["bookId"] in isbns
        assert item["hookLine"] == "테스트 훅 라인"
        assert item["matchedTrait"] == "잔잔함"
        assert item["explanation"] == "테스트 설명"


@respx.mock
def test_recommendations_drops_isbns_missing_from_db(client, db_session):
    token = _login_and_get_token(client)
    known_isbn = "9780000000030"
    _create_book(db_session, known_isbn)

    # ML이 DB에 없는 isbn까지 섞어서 반환하는 경우 — 조용히 걸러져야 한다.
    respx.post(ML_RECOMMEND_URL).mock(
        return_value=httpx.Response(
            200, json=[_ml_item(known_isbn), _ml_item("9999999999999")]
        )
    )

    res = client.get(
        "/api/recommendations", params={"n": 10}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["bookId"] == known_isbn


@respx.mock
def test_recommendations_empty_ml_response_returns_empty_list(client):
    token = _login_and_get_token(client)

    # 온보딩 미완료 등으로 ML에 프로필이 없는 유저 — 빈 리스트 응답
    respx.post(ML_RECOMMEND_URL).mock(return_value=httpx.Response(200, json=[]))

    res = client.get(
        "/api/recommendations", params={"n": 10}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json() == []


@respx.mock
def test_recommendations_ml_server_down_returns_503(client):
    token = _login_and_get_token(client)

    respx.post(ML_RECOMMEND_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    res = client.get(
        "/api/recommendations", params={"n": 10}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 503


@respx.mock
def test_recommendations_malformed_ml_response_returns_503(client, db_session):
    token = _login_and_get_token(client)
    isbn = "9780000000031"
    _create_book(db_session, isbn)

    # ML이 200을 주지만 필수 필드(hook_line 등)가 빠진 스키마 드리프트 상황
    respx.post(ML_RECOMMEND_URL).mock(
        return_value=httpx.Response(200, json=[{"book_id": isbn}])
    )

    res = client.get(
        "/api/recommendations", params={"n": 10}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 503


def test_recommendations_requires_auth(client):
    res = client.get("/api/recommendations")
    assert res.status_code == 401


@respx.mock
def test_similar_books_excludes_source_book(client, db_session):
    source_book = _create_book(db_session, "9780000000040")
    other_a = _create_book(db_session, "9780000000041")
    other_b = _create_book(db_session, "9780000000042")
    review = _create_review_for(db_session, source_book)

    respx.post(ML_SIMILAR_BOOKS_URL).mock(
        return_value=httpx.Response(
            200, json=[_similar_item(other_a.isbn), _similar_item(other_b.isbn)]
        )
    )

    res = client.get(f"/api/reviews/{review.id}/similar-books", params={"n": 5})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert source_book.isbn not in {item["bookId"] for item in body}
    assert all(item["sourceReviewId"] == str(review.id) for item in body)
    assert all(item["matchedReviewSnippet"] == "테스트 인용문" for item in body)
    assert all(item["similarityReason"] == "테스트 이유" for item in body)


def test_similar_books_unknown_review_returns_404(client):
    res = client.get("/api/reviews/00000000-0000-0000-0000-000000000000/similar-books")
    assert res.status_code == 404


@respx.mock
def test_similar_books_ml_server_down_returns_empty_list(client, db_session):
    source_book = _create_book(db_session, "9780000000050")
    review = _create_review_for(db_session, source_book)

    respx.post(ML_SIMILAR_BOOKS_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    res = client.get(f"/api/reviews/{review.id}/similar-books")
    # /recommendations와 달리 이 섹션은 보조 섹션이라 503이 아니라 빈 목록으로
    # 조용히 대체된다(프론트가 isError를 소비하지 않아 UX 차이도 없음).
    assert res.status_code == 200
    assert res.json() == []


@respx.mock
def test_similar_books_malformed_ml_response_returns_empty_list(client, db_session):
    source_book = _create_book(db_session, "9780000000051")
    target_book = _create_book(db_session, "9780000000052")
    review = _create_review_for(db_session, source_book)

    # 필수 필드(snippet/reason)가 빠진 스키마 드리프트 상황
    respx.post(ML_SIMILAR_BOOKS_URL).mock(
        return_value=httpx.Response(200, json=[{"book_id": target_book.isbn}])
    )

    res = client.get(f"/api/reviews/{review.id}/similar-books")
    assert res.status_code == 200
    assert res.json() == []


@respx.mock
def test_similar_books_sends_review_fields_to_ml(client, db_session):
    source_book = _create_book(db_session, "9780000000053")
    review = _create_review_for(
        db_session,
        source_book,
        emotion_tags=["위로", "담백함"],
        liked_points=["문장이 좋았어요"],
        disliked_points=["전개가 느렸어요"],
        content="테스트 본문",
    )

    route = respx.post(ML_SIMILAR_BOOKS_URL).mock(return_value=httpx.Response(200, json=[]))

    client.get(f"/api/reviews/{review.id}/similar-books", params={"n": 7})

    sent_body = route.calls.last.request.content
    payload = json.loads(sent_body)
    assert payload == {
        "isbn": source_book.isbn,
        "emotion_tags": ["위로", "담백함"],
        "liked_points": ["문장이 좋았어요"],
        "disliked_points": ["전개가 느렸어요"],
        "content": "테스트 본문",
        "k": 7,
    }
