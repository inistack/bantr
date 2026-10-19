from app.sockets.presence import run_heartbeat_once
from tests.helpers import add_member, create_ws, socket_connect


def updates(sio_client):
    return [e["args"][0] for e in sio_client.get_received() if e["name"] == "presence.update"]


def presence_list(sio_client, ws):
    return sio_client.emit("presence.list", {"workspace_id": ws}, callback=True)


def event(ws, user, online):
    return {"workspace_id": ws, "user_id": str(user.id), "online": online}


def workspace_with_member(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "bob@test.dev")
    return owner, bob, ws


def test_connecting_announces_the_user_and_appears_in_the_list(app, client, make_user):
    owner, bob, ws = workspace_with_member(client, make_user)
    s_owner = socket_connect(app, owner)
    s_owner.get_received()
    socket_connect(app, bob)
    assert event(ws, bob, True) in updates(s_owner)
    ack = presence_list(s_owner, ws)
    assert ack == {"ok": True, "online": sorted([str(owner.id), str(bob.id)])}


def test_disconnecting_announces_offline(app, client, make_user):
    owner, bob, ws = workspace_with_member(client, make_user)
    s_owner, s_bob = socket_connect(app, owner), socket_connect(app, bob)
    s_owner.get_received()
    s_bob.disconnect()
    assert event(ws, bob, False) in updates(s_owner)
    assert presence_list(s_owner, ws)["online"] == [str(owner.id)]


def test_user_with_two_tabs_goes_offline_only_when_the_last_closes(app, client, make_user):
    owner, bob, ws = workspace_with_member(client, make_user)
    s_owner = socket_connect(app, owner)
    tab1, tab2 = socket_connect(app, bob), socket_connect(app, bob)
    s_owner.get_received()
    tab1.disconnect()
    assert updates(s_owner) == []
    tab2.disconnect()
    assert updates(s_owner) == [event(ws, bob, False)]


def test_non_member_cannot_list_presence(app, client, make_user):
    owner, mallory = make_user("owner@test.dev"), make_user("mallory@test.dev")
    ws = create_ws(client, owner)
    ack = presence_list(socket_connect(app, mallory), ws)
    assert ack["ok"] is False


def test_presence_updates_stay_inside_their_workspace(app, client, make_user):
    alice, bob = make_user("alice@test.dev"), make_user("bob@test.dev")
    create_ws(client, alice, "alpha")
    create_ws(client, bob, "beta")
    s_bob = socket_connect(app, bob)
    s_bob.get_received()
    socket_connect(app, alice)  
    assert updates(s_bob) == []


def test_heartbeat_pass_announces_users_whose_connections_died(app, client, make_user):
    owner, ghost, ws = workspace_with_member(client, make_user)
    s_owner = socket_connect(app, owner)
    s_owner.get_received()
    # Simulate a process that died: an entry that stopped heartbeating long ago.
    app.extensions["redis"].zadd(f"presence:ws:{ws}", {f"{ghost.id}|dead-sid": 1})
    with app.app_context():
        run_heartbeat_once()
    assert event(ws, ghost, False) in updates(s_owner)
