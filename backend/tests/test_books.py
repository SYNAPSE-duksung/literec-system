from app.models import Book


def _create_book(db_session, isbn: str) -> Book:
    book = Book(
        isbn=isbn,
        title=f"테스트 도서 {isbn}",
        author="테스트 작가",
        publisher="테스트 출판사",
        cover_url="https://example.com/cover.jpg",
        synopsis="테스트 시놉시스",
    )
    db_session.add(book)
    db_session.commit()
    return book


def test_list_books_returns_all_books(client, db_session):
    _create_book(db_session, "9780000000001")
    _create_book(db_session, "9780000000002")

    res = client.get("/api/books")
    assert res.status_code == 200
    body = res.json()
    assert {b["id"] for b in body} == {"9780000000001", "9780000000002"}
    assert body[0]["identityVectors"] == []


def test_get_book_by_isbn(client, db_session):
    _create_book(db_session, "9780000000003")

    res = client.get("/api/books/9780000000003")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "9780000000003"
    assert body["title"] == "테스트 도서 9780000000003"
    assert body["identityVectors"] == []


def test_get_book_not_found_returns_404(client):
    res = client.get("/api/books/nonexistent-isbn")
    assert res.status_code == 404
