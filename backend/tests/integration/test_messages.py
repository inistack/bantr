from concurrent.futures import ThreadPoolExecutor

from tests.helpers import create_channel, create_ws, send


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def history(client, user, ws, ch, query=""):
    return client.get(f"/workspaces/{ws}/channels/{ch}/messages{query}", headers=user.headers)


def test_sequence_numbers_increment_from_one(client, make_user):
    owner, ws, ch = setup(client, make_user)
    seqs = [send(client, owner, ws, ch, f"m{i}").get_json()["seq"] for i in range(3)]
    assert seqs == [1, 2, 3]


def test_sequence_is_per_channel(client, make_user):
    owner, ws, ch1 = setup(client, make_user)
    ch2 = create_channel(client, owner, ws, "random")
    send(client, owner, ws, ch1, "a")
    send(client, owner, ws, ch1, "b")
    assert send(client, owner, ws, ch2, "c").get_json()["seq"] == 1


def test_history_is_oldest_first_and_includes_sender(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for body in ["one", "two", "three"]:
        send(client, owner, ws, ch, body)
    msgs = history(client, owner, ws, ch).get_json()
    assert [m["body"] for m in msgs] == ["one", "two", "three"]
    assert msgs[0]["user"]["name"] == "owner"


def test_after_returns_only_newer_messages(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(5):
        send(client, owner, ws, ch, f"m{i}")
    msgs = history(client, owner, ws, ch, "?after=3").get_json()
    assert [m["seq"] for m in msgs] == [4, 5]


def test_before_with_limit_returns_an_older_page(client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(6):
        send(client, owner, ws, ch, f"m{i}")
    msgs = history(client, owner, ws, ch, "?before=5&limit=2").get_json()
    assert [m["seq"] for m in msgs] == [3, 4]


def test_after_and_before_together_is_rejected(client, make_user):
    owner, ws, ch = setup(client, make_user)
    assert history(client, owner, ws, ch, "?after=1&before=3").status_code == 400


def test_empty_or_oversized_body_rejected(client, make_user):
    owner, ws, ch = setup(client, make_user)
    assert send(client, owner, ws, ch, "   ").status_code == 400
    assert send(client, owner, ws, ch, "x" * 4001).status_code == 400


def test_non_integer_cursor_rejected(client, make_user):
    owner, ws, ch = setup(client, make_user)
    assert history(client, owner, ws, ch, "?after=abc").status_code == 400


def test_concurrent_sends_get_distinct_gapfree_seqs(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    path = f"/workspaces/{ws}/channels/{ch}/messages"

    def fire(i):
        # Each thread gets its own client, like separate users on separate connections.
        return app.test_client().post(
            path, json={"body": f"burst {i}"}, headers=owner.headers
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(fire, range(30)))

    assert statuses == [201] * 30
    seqs = [m["seq"] for m in history(client, owner, ws, ch, "?limit=100").get_json()]
    assert seqs == list(range(1, 31))