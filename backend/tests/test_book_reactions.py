from app.models import Book

SIGNUP_PAYLOAD = {"email": "reactor@example.com", "password": "password123", "name": "리액터"}


def _login_and_get_token(client) -> str:
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    return res.json()["access_token"]


def _create_book(db_session, isbn: str) -> Book:
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


def test_like_book_appears_in_book_reactions(client, db_session):
    _create_book(db_session, "9780000000020")
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/books/9780000000020/reaction", json={"reaction": "like"}, headers=headers)
    assert res.status_code == 204

    reactions = client.get("/api/users/me/book-reactions", headers=headers).json()
    assert reactions == {"likedBookIds": ["9780000000020"], "dislikedBookIds": []}


def test_like_then_dislike_is_mutually_exclusive(client, db_session):
    _create_book(db_session, "9780000000021")
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/books/9780000000021/reaction", json={"reaction": "like"}, headers=headers)
    client.post("/api/books/9780000000021/reaction", json={"reaction": "dislike"}, headers=headers)

    reactions = client.get("/api/users/me/book-reactions", headers=headers).json()
    assert reactions == {"likedBookIds": [], "dislikedBookIds": ["9780000000021"]}


def test_delete_reaction_clears_it(client, db_session):
    _create_book(db_session, "9780000000022")
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/books/9780000000022/reaction", json={"reaction": "like"}, headers=headers)
    del_res = client.delete("/api/books/9780000000022/reaction", headers=headers)
    assert del_res.status_code == 204

    reactions = client.get("/api/users/me/book-reactions", headers=headers).json()
    assert reactions == {"likedBookIds": [], "dislikedBookIds": []}


def test_book_reaction_unknown_book_returns_404(client):
    token = _login_and_get_token(client)
    res = client.post(
        "/api/books/nonexistent/reaction",
        json={"reaction": "like"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_book_reaction_requires_auth(client, db_session):
    _create_book(db_session, "9780000000023")
    res = client.post("/api/books/9780000000023/reaction", json={"reaction": "like"})
    assert res.status_code == 401
