from app.extensions import socketio
from tests.helpers import create_channel, create_ws


def connect(app, user):
    token = user.headers["Authorization"].split(" ", 1)[1]
    sio_client = socketio.test_client(app, auth={"token": token})
    assert sio_client.is_connected()
    return sio_client


def join(sio_client, ws, ch):
    return sio_client.emit(
        "channel.join", {"workspace_id": ws, "channel_id": ch}, callback=True
    )


def test_member_can_join_channel_room(app, client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    ack = join(connect(app, owner), ws, ch)
    assert ack["ok"] is True


def test_non_member_cannot_join_channel_room(app, client, make_user):
    owner, mallory = make_user("owner@test.dev"), make_user("mallory@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    ack = join(connect(app, mallory), ws, ch)
    assert ack == {"ok": False, "error": "Channel not found"}


def test_member_of_another_workspace_cannot_join_via_their_own_workspace_id(
    app, client, make_user
):
    alice, bob = make_user("alice@test.dev"), make_user("bob@test.dev")
    alpha = create_ws(client, alice, "alpha")
    beta = create_ws(client, bob, "beta")
    alpha_channel = create_channel(client, alice, alpha)
    # Bob is a real member of Beta, but the channel belongs to Alpha.
    ack = join(connect(app, bob), beta, alpha_channel)
    assert ack == {"ok": False, "error": "Channel not found"}


def test_join_with_malformed_payload_is_refused(app, make_user):
    ack = connect(app, make_user("a@test.dev")).emit(
        "channel.join", {"workspace_id": "nope"}, callback=True
    )
    assert ack["ok"] is False