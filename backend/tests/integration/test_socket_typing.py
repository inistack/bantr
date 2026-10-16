from tests.helpers import add_member, create_channel, create_ws, socket_connect, socket_join


def typing(sio_client, ws, ch):
    return sio_client.emit(
        "user.typing", {"workspace_id": ws, "channel_id": ch}, callback=True
    )


def typing_events(sio_client):
    return [e for e in sio_client.get_received() if e["name"] == "user.typing"]


def two_joined_clients(app, client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    add_member(client, owner, ws, "bob@test.dev")
    s_owner, s_bob = socket_connect(app, owner), socket_connect(app, bob)
    socket_join(s_owner, ws, ch)
    socket_join(s_bob, ws, ch)
    s_owner.get_received()  # discard connect/join events
    s_bob.get_received()
    return bob, ws, ch, s_owner, s_bob


def test_typing_reaches_others_in_the_room_but_not_the_sender(app, client, make_user):
    bob, ws, ch, s_owner, s_bob = two_joined_clients(app, client, make_user)
    assert typing(s_bob, ws, ch) == {"ok": True}
    got = typing_events(s_owner)
    assert len(got) == 1
    assert got[0]["args"][0] == {"channel_id": ch, "user_id": str(bob.id)}
    assert typing_events(s_bob) == []


def test_rapid_typing_events_are_throttled(app, client, make_user):
    _, ws, ch, s_owner, s_bob = two_joined_clients(app, client, make_user)
    assert typing(s_bob, ws, ch) == {"ok": True}
    assert typing(s_bob, ws, ch) == {"ok": True, "throttled": True}
    assert len(typing_events(s_owner)) == 1  # the throttled one was not relayed


def test_typing_requires_joining_the_channel(app, client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    add_member(client, owner, ws, "bob@test.dev")  # a member, but never joins the room
    s_owner, s_bob = socket_connect(app, owner), socket_connect(app, bob)
    socket_join(s_owner, ws, ch)
    s_owner.get_received()

    assert typing(s_bob, ws, ch) == {"ok": False, "error": "Channel not found"}
    assert typing_events(s_owner) == []


def test_typing_with_malformed_payload_is_refused(app, make_user):
    ack = socket_connect(app, make_user("a@test.dev")).emit(
        "user.typing", {"channel_id": "nope"}, callback=True
    )
    assert ack["ok"] is False