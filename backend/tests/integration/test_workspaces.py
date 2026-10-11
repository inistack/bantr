from sqlalchemy import func, select

from app.extensions import db
from app.models import Membership


def create_ws(client, owner, slug="acme"):
    r = client.post(
        "/workspaces", json={"name": slug.title(), "slug": slug}, headers=owner.headers
    )
    assert r.status_code == 201
    return r.get_json()["id"]


def add_member(client, actor, ws, email, role="member"):
    return client.post(
        f"/workspaces/{ws}/members",
        json={"email": email, "role": role},
        headers=actor.headers,
    )


def test_workspaces_require_login(client):
    assert client.get("/workspaces").status_code == 401


def test_creator_becomes_owner(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    r = client.get(f"/workspaces/{ws}", headers=owner.headers)
    assert r.status_code == 200
    assert r.get_json()["role"] == "owner"


def test_non_member_gets_404_not_403(client, make_user):
    owner, outsider = make_user("owner@test.dev"), make_user("out@test.dev")
    ws = create_ws(client, owner)
    r = client.get(f"/workspaces/{ws}", headers=outsider.headers)
    assert r.status_code == 404


def test_owner_can_add_member_who_can_then_view(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    assert add_member(client, owner, ws, "bob@test.dev").status_code == 201
    r = client.get(f"/workspaces/{ws}", headers=bob.headers)
    assert r.status_code == 200
    assert r.get_json()["role"] == "member"


def test_member_cannot_add_members(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    make_user("carol@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "bob@test.dev")
    assert add_member(client, bob, ws, "carol@test.dev").status_code == 403


def test_owner_cannot_grant_owner_role(client, make_user):
    owner = make_user("owner@test.dev")
    make_user("carol@test.dev")
    ws = create_ws(client, owner)
    assert add_member(client, owner, ws, "carol@test.dev", "owner").status_code == 403


def test_admin_can_add_members_but_not_other_admins(client, make_user):
    owner, carol = make_user("owner@test.dev"), make_user("carol@test.dev")
    make_user("dave@test.dev")
    make_user("eve@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "carol@test.dev", "admin")
    assert add_member(client, carol, ws, "dave@test.dev", "member").status_code == 201
    assert add_member(client, carol, ws, "eve@test.dev", "admin").status_code == 403


def test_adding_same_member_twice_conflicts(client, make_user):
    owner = make_user("owner@test.dev")
    make_user("bob@test.dev")
    ws = create_ws(client, owner)
    assert add_member(client, owner, ws, "bob@test.dev").status_code == 201
    assert add_member(client, owner, ws, "bob@test.dev").status_code == 409


def test_duplicate_slug_conflicts(client, make_user):
    owner = make_user("owner@test.dev")
    create_ws(client, owner, "acme")
    r = client.post(
        "/workspaces", json={"name": "Other", "slug": "acme"}, headers=owner.headers
    )
    assert r.status_code == 409


def test_only_owner_can_delete_and_memberships_cascade(app, client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    add_member(client, owner, ws, "bob@test.dev")

    assert client.delete(f"/workspaces/{ws}", headers=bob.headers).status_code == 403
    assert client.delete(f"/workspaces/{ws}", headers=owner.headers).status_code == 204

    with app.app_context():
        remaining = db.session.scalar(select(func.count()).select_from(Membership))
    assert remaining == 0