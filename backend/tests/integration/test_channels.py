from sqlalchemy import func, select

from app.extensions import db
from app.models import Message
from tests.helpers import add_member, create_channel, create_ws, send


def test_member_can_list_channels(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    create_channel(client, owner, ws, "general")
    add_member(client, owner, ws, "bob@test.dev")
    r = client.get(f"/workspaces/{ws}/channels", headers=bob.headers)
    assert r.status_code == 200
    assert [c["name"] for c in r.get_json()] == ["general"]


def test_non_member_cannot_list_channels(client, make_user):
    owner, outsider = make_user("owner@test.dev"), make_user("out@test.dev")
    ws = create_ws(client, owner)
    assert client.get(f"/workspaces/{ws}/channels", headers=outsider.headers).status_code == 404


def test_member_cannot_create_channel(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "bob@test.dev")
    r = client.post(f"/workspaces/{ws}/channels", json={"name": "x"}, headers=bob.headers)
    assert r.status_code == 403


def test_admin_can_create_channel(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "bob@test.dev", "admin")
    r = client.post(f"/workspaces/{ws}/channels", json={"name": "ops"}, headers=bob.headers)
    assert r.status_code == 201


def test_invalid_channel_name_rejected(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    for bad in ["Bad Name!", "", "-leading", "trailing-", "a" * 81]:
        r = client.post(f"/workspaces/{ws}/channels", json={"name": bad}, headers=owner.headers)
        assert r.status_code == 400, bad


def test_duplicate_channel_name_conflicts_within_workspace(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    create_channel(client, owner, ws, "general")
    r = client.post(f"/workspaces/{ws}/channels", json={"name": "general"}, headers=owner.headers)
    assert r.status_code == 409


def test_same_channel_name_allowed_in_different_workspaces(client, make_user):
    a, b = make_user("a@test.dev"), make_user("b@test.dev")
    create_channel(client, a, create_ws(client, a, "alpha"), "general")
    create_channel(client, b, create_ws(client, b, "beta"), "general")  # asserts 201


def test_deleting_channel_removes_its_messages(app, client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    send(client, owner, ws, ch, "hello")
    r = client.delete(f"/workspaces/{ws}/channels/{ch}", headers=owner.headers)
    assert r.status_code == 204
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Message)) == 0