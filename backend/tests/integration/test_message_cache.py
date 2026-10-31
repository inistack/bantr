import redis

from prometheus_client import REGISTRY
from tests.helpers import create_channel, create_ws, send


class BrokenRedis:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise redis.ConnectionError("redis is down")
        return fail


def cache_key(ws, ch):
    return f"msgs:ws:{ws}:ch:{ch}"


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def history(client, user, ws, ch, query=""):
    return client.get(f"/workspaces/{ws}/channels/{ch}/messages{query}", headers=user.headers)


def stats():
    def count(result):
        return REGISTRY.get_sample_value(
            "bantr_message_cache_requests_total", {"result": result}
        ) or 0.0
    return count("hit"), count("miss")


def test_second_read_is_served_from_the_cache(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(3):
        send(client, owner, ws, ch, f"m{i}")
    h0, m0 = stats()
    first = history(client, owner, ws, ch).get_json()
    second = history(client, owner, ws, ch).get_json()
    h1, m1 = stats()
    assert (m1 - m0, h1 - h0) == (1, 1)
    assert first == second
    assert [m["body"] for m in second] == ["m0", "m1", "m2"]


def test_a_new_message_is_never_hidden_by_a_warm_cache(client, make_user):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m0")
    history(client, owner, ws, ch)  # warms the cache
    send(client, owner, ws, ch, "m1")
    assert [m["body"] for m in history(client, owner, ws, ch).get_json()] == ["m0", "m1"]


def test_a_small_limit_is_served_from_the_cached_window(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(5):
        send(client, owner, ws, ch, f"m{i}")
    history(client, owner, ws, ch, "?limit=2")  # miss: fills the whole window
    h0, _ = stats()
    got = history(client, owner, ws, ch, "?limit=2").get_json()
    assert stats()[0] - h0 == 1
    assert [m["body"] for m in got] == ["m3", "m4"]


def test_a_limit_above_the_cache_size_is_correct_and_does_not_truncate_later_reads(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(60):
        send(client, owner, ws, ch, f"m{i}")
    big = history(client, owner, ws, ch, "?limit=60").get_json()
    assert [m["seq"] for m in big] == list(range(1, 61))
    default = history(client, owner, ws, ch).get_json()
    assert [m["seq"] for m in default] == list(range(11, 61))


def test_a_warm_cache_is_not_reachable_through_another_workspace(client, make_user):
    alice, bob = make_user("alice@test.dev"), make_user("bob@test.dev")
    alpha, beta = create_ws(client, alice, "alpha"), create_ws(client, bob, "beta")
    ch = create_channel(client, alice, alpha)
    send(client, alice, alpha, ch, "secret")
    history(client, alice, alpha, ch)  # warm
    r = history(client, bob, beta, ch)  # Bob's own workspace id, Alice's channel
    assert r.status_code == 404
    assert "secret" not in r.get_data(as_text=True)


def test_reads_still_work_when_redis_is_down(app, client, make_user, monkeypatch):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m0")
    monkeypatch.setitem(app.extensions, "redis", BrokenRedis())
    r = history(client, owner, ws, ch)
    assert r.status_code == 200
    assert [m["body"] for m in r.get_json()] == ["m0"]


def test_a_read_after_a_send_is_a_cache_hit(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(3):
        send(client, owner, ws, ch, f"m{i}")
    history(client, owner, ws, ch)  # miss: warms the cache
    send(client, owner, ws, ch, "m3")
    h0, m0 = stats()
    got = history(client, owner, ws, ch).get_json()
    h1, m1 = stats()
    assert (h1 - h0, m1 - m0) == (1, 0)
    assert [m["body"] for m in got] == ["m0", "m1", "m2", "m3"]


def test_sending_to_a_cold_channel_does_not_create_a_cache(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m0")
    assert app.extensions["redis"].exists(cache_key(ws, ch)) == 0


def test_cached_and_rebuilt_results_are_identical(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(3):
        send(client, owner, ws, ch, f"m{i}")
    history(client, owner, ws, ch)           # warm
    send(client, owner, ws, ch, "m3")        # write-through
    from_cache = history(client, owner, ws, ch).get_json()
    app.extensions["redis"].delete(cache_key(ws, ch))
    rebuilt = history(client, owner, ws, ch).get_json()
    assert from_cache == rebuilt


def test_sending_still_works_when_redis_is_down(app, client, make_user, monkeypatch):
    owner, ws, ch = setup(client, make_user)
    monkeypatch.setitem(app.extensions, "redis", BrokenRedis())
    assert send(client, owner, ws, ch, "while redis is down").status_code == 201


def test_with_the_cache_turned_off_reads_never_touch_it(app, client, make_user, monkeypatch):
    monkeypatch.setitem(app.config, "MESSAGE_CACHE_ENABLED", False)
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m0")
    before = stats()
    r = history(client, owner, ws, ch)
    assert [m["body"] for m in r.get_json()] == ["m0"]
    assert stats() == before
    assert app.extensions["redis"].exists(cache_key(ws, ch)) == 0


def test_a_server_that_skips_the_cache_cannot_make_it_serve_stale_data(
    app, client, make_user, monkeypatch
):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m0")
    history(client, owner, ws, ch)  
    with monkeypatch.context() as patch:
        patch.setitem(app.config, "MESSAGE_CACHE_ENABLED", False)
        send(client, owner, ws, ch, "m1")  
    assert [m["body"] for m in history(client, owner, ws, ch).get_json()] == ["m0", "m1"]