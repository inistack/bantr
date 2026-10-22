import pytest

from app.rate_limit import limiter, rate_limit_key
from tests.helpers import add_member, create_channel, create_ws, send


@pytest.fixture
def tight_limit(app, monkeypatch):
    monkeypatch.setitem(app.config, "MESSAGE_RATE_LIMIT", "3 per minute")
    limiter.reset()
    yield
    limiter.reset()


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def test_key_is_the_user_when_there_is_a_token_and_the_ip_otherwise(app, make_user):
    user = make_user("a@test.dev")
    with app.test_request_context("/", headers=user.headers):
        assert rate_limit_key() == f"user:{user.id}"
    with app.test_request_context(
        "/", headers={"Authorization": "Bearer junk"}, environ_base={"REMOTE_ADDR": "9.9.9.9"}
    ):
        assert rate_limit_key() == "ip:9.9.9.9"


def test_sends_over_the_limit_get_429(client, make_user, tight_limit):
    owner, ws, ch = setup(client, make_user)
    statuses = [send(client, owner, ws, ch, f"m{i}").status_code for i in range(5)]
    assert statuses == [201, 201, 201, 429, 429]
    assert "Too many requests" in send(client, owner, ws, ch, "x").get_json()["error"]


def test_the_limit_is_per_user(client, make_user, tight_limit):
    owner, ws, ch = setup(client, make_user)
    bob = make_user("bob@test.dev")
    add_member(client, owner, ws, "bob@test.dev")
    for i in range(3):
        send(client, owner, ws, ch, f"m{i}")
    assert send(client, owner, ws, ch, "over").status_code == 429
    assert send(client, bob, ws, ch, "still fine").status_code == 201


def test_rejected_sends_are_not_stored(client, make_user, tight_limit):
    owner, ws, ch = setup(client, make_user)
    for i in range(5):
        send(client, owner, ws, ch, f"m{i}")
    r = client.get(f"/workspaces/{ws}/channels/{ch}/messages", headers=owner.headers)
    assert [m["seq"] for m in r.get_json()] == [1, 2, 3]


def test_reads_are_not_limited(client, make_user, tight_limit):
    owner, ws, ch = setup(client, make_user)
    for i in range(4):
        send(client, owner, ws, ch, f"m{i}")
    for _ in range(10):
        r = client.get(f"/workspaces/{ws}/channels/{ch}/messages", headers=owner.headers)
        assert r.status_code == 200


def test_unauthenticated_floods_are_limited_by_ip(client, make_user, tight_limit):
    owner, ws, ch = setup(client, make_user)
    statuses = [
        client.post(f"/workspaces/{ws}/channels/{ch}/messages", json={"body": "hi"}).status_code
        for _ in range(5)
    ]
    assert statuses == [401, 401, 401, 429, 429]