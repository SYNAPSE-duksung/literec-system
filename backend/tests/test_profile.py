SIGNUP_PAYLOAD = {"email": "profile@example.com", "password": "password123", "name": "프로필"}


def _login_and_get_token(client) -> str:
    client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)
    res = client.post(
        "/api/auth/login",
        json={"email": SIGNUP_PAYLOAD["email"], "password": SIGNUP_PAYLOAD["password"]},
    )
    return res.json()["access_token"]


def test_get_profile_before_onboarding_returns_empty_arrays(client):
    token = _login_and_get_token(client)
    res = client.get("/api/users/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["preferredEmotions"] == []
    assert body["avoidedTraits"] == []


def test_patch_profile_creates_row_on_first_call(client):
    token = _login_and_get_token(client)
    res = client.patch(
        "/api/users/me/profile",
        json={"preferredEmotions": ["잔잔함", "위로"], "avoidedTraits": ["신파"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["preferredEmotions"] == ["잔잔함", "위로"]
    assert body["avoidedTraits"] == ["신파"]


def test_patch_profile_partial_update_keeps_other_field(client):
    token = _login_and_get_token(client)
    client.patch(
        "/api/users/me/profile",
        json={"preferredEmotions": ["잔잔함"], "avoidedTraits": ["신파"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    res = client.patch(
        "/api/users/me/profile",
        json={"preferredEmotions": ["설렘"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["preferredEmotions"] == ["설렘"]
    assert body["avoidedTraits"] == ["신파"]


def test_profile_requires_auth(client):
    res = client.get("/api/users/me/profile")
    assert res.status_code == 401
