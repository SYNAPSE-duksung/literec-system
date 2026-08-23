from app.models import Book, RecommendationEvent

SIGNUP_PAYLOAD = {"email": "events@example.com", "password": "password123", "name": "이벤트"}


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
        title=f"테스트 도서 {isbn}",
        author="테스트 작가",
        publisher="테스트 출판사",
        cover_url=None,
        synopsis=None,
    )
    db_session.add(book)
    db_session.commit()
    return book


def test_log_impression_event_succeeds(client, db_session):
    token = _login_and_get_token(client)
    book = _create_book(db_session, "9780000000050")

    res = client.post(
        "/api/events",
        json={"book_id": book.isbn, "event_type": "impression", "source": "home", "rank": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json() == {"status": "ok"}

    events = db_session.query(RecommendationEvent).filter(
        RecommendationEvent.book_id == book.isbn
    ).all()
    assert len(events) == 1
    assert events[0].event_type == "impression"
    assert events[0].rank == 1


def test_log_click_event_with_rank_succeeds(client, db_session):
    """rank는 impression 전용이 아니라 클릭 이벤트에도 함께 쓰인다(app/src/pages/HomePage.tsx)."""
    token = _login_and_get_token(client)
    book = _create_book(db_session, "9780000000051")

    res = client.post(
        "/api/events",
        json={"book_id": book.isbn, "event_type": "click", "source": "home", "rank": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201


def test_log_event_unknown_book_id_returns_404(client):
    token = _login_and_get_token(client)

    res = client.post(
        "/api/events",
        json={"book_id": "존재하지-않는-isbn", "event_type": "impression", "source": "home", "rank": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_log_event_invalid_event_type_returns_422(client):
    token = _login_and_get_token(client)

    res = client.post(
        "/api/events",
        json={"book_id": "9780000000052", "event_type": "not-a-real-type", "source": "home"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422


def test_log_event_requires_auth(client):
    res = client.post(
        "/api/events",
        json={"book_id": "9780000000053", "event_type": "impression", "source": "home"},
    )
    assert res.status_code == 401
