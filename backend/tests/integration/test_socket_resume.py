from tests.helpers import create_channel, create_ws, send, socket_connect


def join_after(sio_client, ws, ch, after=None):
    payload = {"workspace_id": ws, "channel_id": ch}
    if after is not None:
        payload["after_seq"] = after
    return sio_client.emit("channel.join", payload, callback=True)


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def test_join_with_after_seq_returns_missed_messages_in_order(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(1, 6):
        send(client, owner, ws, ch, f"m{i}")
    ack = join_after(socket_connect(app, owner), ws, ch, after=2)
    assert ack["ok"] is True
    assert [m["seq"] for m in ack["missed"]] == [3, 4, 5]
    assert [m["body"] for m in ack["missed"]] == ["m3", "m4", "m5"]
    assert ack["has_more"] is False
    assert ack["last_seq"] == 5


def test_join_without_after_seq_has_no_history(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "old")
    ack = join_after(socket_connect(app, owner), ws, ch)
    assert ack["ok"] is True
    assert "missed" not in ack
    assert ack["last_seq"] == 1


def test_resume_when_already_caught_up_returns_nothing(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "m1")
    ack = join_after(socket_connect(app, owner), ws, ch, after=1)
    assert ack["missed"] == []
    assert ack["has_more"] is False


def test_resume_pages_at_100_and_says_there_is_more(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    for i in range(101):
        send(client, owner, ws, ch, f"m{i}")
    ack = join_after(socket_connect(app, owner), ws, ch, after=0)
    assert len(ack["missed"]) == 100
    assert ack["missed"][0]["seq"] == 1 and ack["missed"][-1]["seq"] == 100
    assert ack["has_more"] is True


def test_resume_only_returns_messages_from_that_channel(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    other = create_channel(client, owner, ws, "random")
    send(client, owner, ws, ch, "in general")
    send(client, owner, ws, other, "in random")
    ack = join_after(socket_connect(app, owner), ws, ch, after=0)
    assert [m["body"] for m in ack["missed"]] == ["in general"]


def test_non_member_cannot_read_history_through_resume(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    mallory = make_user("mallory@test.dev")
    send(client, owner, ws, ch, "secret")
    ack = join_after(socket_connect(app, mallory), ws, ch, after=0)
    assert ack == {"ok": False, "error": "Channel not found"}


def test_invalid_after_seq_is_rejected(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    s = socket_connect(app, owner)
    for bad in [-1, "3", 1.5, True]:
        assert join_after(s, ws, ch, after=bad)["ok"] is False, bad


def test_live_messages_still_arrive_after_a_resume_join(app, client, make_user):
    owner, ws, ch = setup(client, make_user)
    s = socket_connect(app, owner)
    join_after(s, ws, ch, after=0)
    s.get_received()
    send(client, owner, ws, ch, "live")
    got = [e for e in s.get_received() if e["name"] == "message.sent"]
    assert [e["args"][0]["message"]["seq"] for e in got] == [1]