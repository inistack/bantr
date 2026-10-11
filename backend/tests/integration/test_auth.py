from datetime import datetime, timedelta, timezone

import jwt


def test_me_requires_a_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_me_returns_current_user(client, make_user):
    user = make_user("ada@test.dev")
    r = client.get("/auth/me", headers=user.headers)
    assert r.status_code == 200
    assert r.get_json()["email"] == "ada@test.dev"


def test_expired_token_is_rejected(app, client, make_user):
    user = make_user("ada@test.dev")
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_token_signed_with_wrong_secret_is_rejected(client, make_user):
    user = make_user("ada@test.dev")
    forged = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "some-attackers-guess-that-is-long-enough",
        algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401