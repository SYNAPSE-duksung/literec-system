from app.models import Book, Review

SIGNUP_PAYLOAD = {"email": "rec@example.com", "password": "password123", "name": "추천"}


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


def test_recommendations_returns_at_most_n_books(client, db_session):
    for i in range(5):
        _create_book(db_session, f"978000000{i:02d}A")

    res = client.get("/api/recommendations", params={"n": 3})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 3
    for item in body:
        assert "bookId" in item
        assert "hookLine" in item
        assert "matchedTrait" in item
        assert "explanation" in item


def test_recommendations_caps_at_available_book_count(client, db_session):
    _create_book(db_session, "9780000000030")
    _create_book(db_session, "9780000000031")

    res = client.get("/api/recommendations", params={"n": 10})
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_similar_books_excludes_source_book(client, db_session):
    source_book = _create_book(db_session, "9780000000040")
    _create_book(db_session, "9780000000041")
    _create_book(db_session, "9780000000042")

    review = Review(
        isbn=source_book.isbn,
        user_id=None,
        source="llm_generated",
        persona="테스트 페르소나",
        content="테스트 리뷰",
    )
    db_session.add(review)
    db_session.commit()
    db_session.refresh(review)

    res = client.get(f"/api/reviews/{review.id}/similar-books", params={"n": 5})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 2
    assert source_book.isbn not in {item["bookId"] for item in body}
    assert all(item["sourceReviewId"] == str(review.id) for item in body)


def test_similar_books_unknown_review_returns_404(client):
    res = client.get("/api/reviews/00000000-0000-0000-0000-000000000000/similar-books")
    assert res.status_code == 404
