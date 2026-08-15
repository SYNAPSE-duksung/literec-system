SIGNUP_PAYLOAD = {"email": "tester@example.com", "password": "password123", "name": "테스터"}


def test_signup_success(client):
    res = client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == SIGNUP_PAYLOAD["email"]
    assert body["name"] == SIGNUP_PAYLOAD["name"]
    assert "id" in body


def test_signup_duplicate_email_rejected(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    assert res.status_code == 409


def test_login_returns_access_token_and_refresh_cookie(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["user"]["email"] == SIGNUP_PAYLOAD["email"]
    assert res.cookies.get("refresh_token") is not None


def test_login_wrong_password_rejected(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": "wrong-password"},
    )
    assert res.status_code == 401


def test_me_requires_valid_access_token(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    login_res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    access_token = login_res.json()["access_token"]

    no_auth_res = client.get("/api/auth/me")
    assert no_auth_res.status_code == 401

    ok_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert ok_res.status_code == 200
    assert ok_res.json()["email"] == SIGNUP_PAYLOAD["email"]


def test_refresh_issues_new_access_token(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    res = client.post("/api/auth/refresh")
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_logout_revokes_refresh_token(client):
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 204

    refresh_res = client.post("/api/auth/refresh")
    assert refresh_res.status_code == 401
