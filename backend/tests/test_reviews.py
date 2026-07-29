from app.models import Book

SIGNUP_PAYLOAD = {"email": "reviewer@example.com", "password": "password123", "name": "리뷰어"}


def _login_and_get_token(client) -> str:
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    return res.json()["access_token"]


def _create_book(db_session, isbn: str = "9780000000010") -> Book:
    book = Book(
        isbn=isbn,
        title="테스트 도서",
        author="테스트 작가",
        publisher="테스트 출판사",
        cover_url=None,
        synopsis=None,
    )
    db_session.add(book)
    db_session.commit()
    return book


def test_create_review_and_get_by_id(client, db_session):
    _create_book(db_session)
    token = _login_and_get_token(client)

    create_res = client.post(
        "/api/reviews",
        json={
            "isbn": "9780000000010",
            "content": "정말 좋았어요",
            "emotion": ["잔잔함"],
            "liked": ["문체"],
            "disliked": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["bookId"] == "9780000000010"
    assert body["userName"] == SIGNUP_PAYLOAD["name"]
    assert body["liked"] == ["문체"]
    assert body["emotion"] == ["잔잔함"]
    assert body["likeCount"] == 0

    get_res = client.get(f"/api/reviews/{body['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["content"] == "정말 좋았어요"


def test_create_review_requires_auth(client, db_session):
    _create_book(db_session)
    res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000010", "content": "내용", "emotion": [], "liked": [], "disliked": []},
    )
    assert res.status_code == 401


def test_create_review_unknown_book_returns_404(client):
    token = _login_and_get_token(client)
    res = client.post(
        "/api/reviews",
        json={"isbn": "nonexistent", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_list_reviews_by_book(client, db_session):
    _create_book(db_session, "9780000000011")
    _create_book(db_session, "9780000000012")
    token = _login_and_get_token(client)
    client.post(
        "/api/reviews",
        json={"isbn": "9780000000011", "content": "리뷰 A", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/reviews",
        json={"isbn": "9780000000012", "content": "리뷰 B", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/api/books/9780000000011/reviews")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["content"] == "리뷰 A"


def test_list_reviews_with_filter(client, db_session):
    _create_book(db_session, "9780000000013")
    token = _login_and_get_token(client)
    client.post(
        "/api/reviews",
        json={
            "isbn": "9780000000013",
            "content": "잔잔한 이야기였어요",
            "emotion": [],
            "liked": [],
            "disliked": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/reviews",
        json={
            "isbn": "9780000000013",
            "content": "몰입감 있게 읽었습니다",
            "emotion": [],
            "liked": [],
            "disliked": [],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/api/reviews", params={"filter": "잔잔"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert "잔잔" in body[0]["content"]


def test_review_reaction_toggle_and_mutual_exclusivity(client, db_session):
    _create_book(db_session, "9780000000014")
    token = _login_and_get_token(client)
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000014", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    review_id = create_res.json()["id"]
    headers = {"Authorization": f"Bearer {token}"}

    like_res = client.post(f"/api/reviews/{review_id}/reaction", json={"reaction": "like"}, headers=headers)
    assert like_res.status_code == 204
    after_like = client.get(f"/api/reviews/{review_id}").json()
    assert after_like["likeCount"] == 1

    dislike_res = client.post(
        f"/api/reviews/{review_id}/reaction", json={"reaction": "dislike"}, headers=headers
    )
    assert dislike_res.status_code == 204
    after_dislike = client.get(f"/api/reviews/{review_id}").json()
    assert after_dislike["likeCount"] == 0

    reactions_res = client.get("/api/users/me/review-reactions", headers=headers)
    assert reactions_res.status_code == 200
    assert reactions_res.json()[review_id] == "dislike"

    clear_res = client.delete(f"/api/reviews/{review_id}/reaction", headers=headers)
    assert clear_res.status_code == 204
    reactions_after_clear = client.get("/api/users/me/review-reactions", headers=headers)
    assert reactions_after_clear.json() == {}
