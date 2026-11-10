import pytest
from authlib.integrations.base_client import OAuthError

from app.extensions import oauth

PROFILE = {
    "id": 4242,
    "login": "ada",
    "name": "Ada Lovelace",
    "avatar_url": "https://example.test/a.png",
}
VERIFIED = [{"email": "ada@example.test", "primary": True, "verified": True}]
UNVERIFIED = [{"email": "ada@example.test", "primary": True, "verified": False}]


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


@pytest.fixture
def fake_github(monkeypatch):
    """Stand in for GitHub: no network, we choose what 'GitHub' answers."""

    def install(emails=VERIFIED, error=None):
        def authorize_access_token():
            if error:
                raise error
            return {"access_token": "gho_fake", "token_type": "bearer"}

        def get(path, token=None, **kwargs):
            return FakeResponse(PROFILE if path == "user" else emails)

        monkeypatch.setattr(oauth.github, "authorize_access_token", authorize_access_token)
        monkeypatch.setattr(oauth.github, "get", get)

    return install


def login_cookies(response):
    return [c for c in response.headers.getlist("Set-Cookie") if c.startswith("bantr_token=")]


def test_a_successful_github_login_sets_the_cookie_and_redirects_into_the_app(client, fake_github):
    fake_github()
    r = client.get("/auth/github/callback")
    assert r.status_code == 302 and r.headers["Location"] == "/"
    (cookie,) = login_cookies(r)
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.get_json()["email"] == "ada@example.test"


def test_an_unverified_email_is_refused_without_a_cookie(client, fake_github):
    fake_github(emails=UNVERIFIED)
    r = client.get("/auth/github/callback")
    assert r.status_code == 302 and r.headers["Location"] == "/?login_error=no_verified_email"
    assert login_cookies(r) == []


def test_a_github_failure_redirects_with_an_error_and_no_cookie(client, fake_github):
    fake_github(error=OAuthError(error="access_denied"))
    r = client.get("/auth/github/callback")
    assert r.status_code == 302 and r.headers["Location"] == "/?login_error=provider"
    assert login_cookies(r) == []


def test_dev_login_does_not_exist_unless_enabled(client):
    assert client.post("/auth/dev-login", json={"email": "a@test.dev"}).status_code == 404


def test_dev_login_signs_in_and_creates_the_user(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "DEV_LOGIN_ENABLED", True)
    r = client.post("/auth/dev-login", json={"email": "New@Test.dev"})
    assert r.status_code == 200 and "HttpOnly" in login_cookies(r)[0]
    assert client.get("/auth/me").get_json()["email"] == "new@test.dev"


def test_dev_login_rejects_a_bad_email(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "DEV_LOGIN_ENABLED", True)
    assert client.post("/auth/dev-login", json={"email": "nope"}).status_code == 400
