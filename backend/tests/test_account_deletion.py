from app.models import Book, Review

SIGNUP_PAYLOAD = {"email": "leaving@example.com", "password": "password123", "name": "탈퇴자"}


def _login_and_get_token(client) -> str:
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    return res.json()["access_token"]


def _create_book(db_session, isbn: str = "9780000000020") -> Book:
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


def test_delete_account_requires_auth(client):
    res = client.delete("/api/users/me")
    assert res.status_code == 401


def test_delete_account_succeeds_and_removes_login(client):
    token = _login_and_get_token(client)
    res = client.delete("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 204

    login_res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    assert login_res.status_code == 401


def test_delete_account_with_profile_and_reactions_does_not_error(client, db_session):
    book = _create_book(db_session)
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.patch(
        "/api/users/me/profile",
        json={"preferredEmotions": ["잔잔함"], "avoidedTraits": ["신파"]},
        headers=headers,
    )
    client.post(f"/api/books/{book.isbn}/reaction", json={"reaction": "like"}, headers=headers)

    res = client.delete("/api/users/me", headers=headers)
    assert res.status_code == 204


def test_delete_account_orphans_review_instead_of_deleting_it(client, db_session):
    book = _create_book(db_session)
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/api/reviews",
        json={"isbn": book.isbn, "content": "탈퇴 전에 남긴 기록", "emotion": [], "liked": [], "disliked": []},
        headers=headers,
    )
    review_id = create_res.json()["id"]

    res = client.delete("/api/users/me", headers=headers)
    assert res.status_code == 204

    get_res = client.get(f"/api/reviews/{review_id}")
    assert get_res.status_code == 200
    assert get_res.json()["content"] == "탈퇴 전에 남긴 기록"

    db_session.expire_all()
    review = db_session.get(Review, review_id)
    assert review.user_id is None
