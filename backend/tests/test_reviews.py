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


def test_update_own_review_succeeds(client, db_session):
    _create_book(db_session, "9780000000018")
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_res = client.post(
        "/api/reviews",
        json={
            "isbn": "9780000000018",
            "content": "처음 내용",
            "emotion": ["잔잔함"],
            "liked": ["문체"],
            "disliked": [],
        },
        headers=headers,
    )
    review_id = create_res.json()["id"]

    update_res = client.patch(
        f"/api/reviews/{review_id}",
        json={
            "content": "고친 내용",
            "emotion": ["몰입감"],
            "liked": ["결말"],
            "disliked": ["전개"],
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    body = update_res.json()
    assert body["content"] == "고친 내용"
    assert body["emotion"] == ["몰입감"]
    assert body["liked"] == ["결말"]
    assert body["disliked"] == ["전개"]
    assert body["bookId"] == "9780000000018"  # isbn은 그대로 유지

    get_res = client.get(f"/api/reviews/{review_id}")
    assert get_res.json()["content"] == "고친 내용"


def test_update_review_requires_auth(client, db_session):
    _create_book(db_session, "9780000000019")
    token = _login_and_get_token(client)
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000019", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    review_id = create_res.json()["id"]

    res = client.patch(f"/api/reviews/{review_id}", json={"content": "수정 시도"})
    assert res.status_code == 401


def test_update_others_review_returns_403(client, db_session):
    _create_book(db_session, "9780000000020")
    owner_token = _login_and_get_token(client)
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000020", "content": "원본", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    review_id = create_res.json()["id"]

    client.post(
        "/api/auth/signup",
        json={"email": "editor-other@example.com", "password": "password123", "name": "다른사람"},
    )
    other_login = client.post(
        "/api/auth/login", json={"email": "editor-other@example.com", "password": "password123"}
    )
    other_token = other_login.json()["access_token"]

    res = client.patch(
        f"/api/reviews/{review_id}",
        json={"content": "몰래 수정", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res.status_code == 403

    get_res = client.get(f"/api/reviews/{review_id}")
    assert get_res.json()["content"] == "원본"


def test_update_unknown_review_returns_404(client):
    token = _login_and_get_token(client)
    res = client.patch(
        "/api/reviews/00000000-0000-0000-0000-000000000000",
        json={"content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404


def test_delete_own_review_succeeds(client, db_session):
    _create_book(db_session, "9780000000015")
    token = _login_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000015", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers=headers,
    )
    review_id = create_res.json()["id"]

    # 삭제 전에 스스로 좋아요를 남겨서 review_reactions FK 정리까지 함께 검증한다.
    client.post(f"/api/reviews/{review_id}/reaction", json={"reaction": "like"}, headers=headers)

    delete_res = client.delete(f"/api/reviews/{review_id}", headers=headers)
    assert delete_res.status_code == 204

    get_res = client.get(f"/api/reviews/{review_id}")
    assert get_res.status_code == 404


def test_delete_review_requires_auth(client, db_session):
    _create_book(db_session, "9780000000016")
    token = _login_and_get_token(client)
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000016", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    review_id = create_res.json()["id"]

    res = client.delete(f"/api/reviews/{review_id}")
    assert res.status_code == 401


def test_delete_others_review_returns_403(client, db_session):
    _create_book(db_session, "9780000000017")
    owner_token = _login_and_get_token(client)
    create_res = client.post(
        "/api/reviews",
        json={"isbn": "9780000000017", "content": "내용", "emotion": [], "liked": [], "disliked": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    review_id = create_res.json()["id"]

    client.post("/api/auth/signup", json={"email": "other@example.com", "password": "password123", "name": "다른사람"})
    other_login = client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "password123"}
    )
    other_token = other_login.json()["access_token"]

    res = client.delete(f"/api/reviews/{review_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert res.status_code == 403

    get_res = client.get(f"/api/reviews/{review_id}")
    assert get_res.status_code == 200


def test_delete_unknown_review_returns_404(client):
    token = _login_and_get_token(client)
    res = client.delete(
        "/api/reviews/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
