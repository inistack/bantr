import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.errors import NotFound
from app.extensions import db
from app.models import Channel, Membership, Message, User, Workspace
from app.services.scoping import get_in_workspace, scoped_select
from tests.helpers import add_member, create_channel, create_ws, send

SECRET_A, SECRET_B = "ALPHA-SECRET-7f3a", "BETA-SECRET-91bc"


@pytest.fixture
def tenants(client, make_user):
    """Two workspaces with different owners, one channel and one message each,
    plus `multi`, an admin in BOTH (the case that makes tenancy interesting)."""
    alice, bob, multi = (make_user(f"{n}@test.dev") for n in ("alice", "bob", "multi"))
    a, b = create_ws(client, alice, "alpha"), create_ws(client, bob, "beta")
    ch_a = create_channel(client, alice, a, "alpha-general")
    ch_b = create_channel(client, bob, b, "beta-general")
    send(client, alice, a, ch_a, SECRET_A)
    send(client, bob, b, ch_b, SECRET_B)
    add_member(client, alice, a, "multi@test.dev", "admin")
    add_member(client, bob, b, "multi@test.dev", "admin")
    return SimpleNamespace(
        alice=alice, bob=bob, multi=multi, a=a, b=b, ch_a=ch_a, ch_b=ch_b
    )


ENDPOINTS = [
    ("GET", "/workspaces/{ws}", None),
    ("GET", "/workspaces/{ws}/members", None),
    ("POST", "/workspaces/{ws}/members", {"email": "x@test.dev"}),
    ("DELETE", "/workspaces/{ws}", None),
    ("GET", "/workspaces/{ws}/channels", None),
    ("POST", "/workspaces/{ws}/channels", {"name": "intruder"}),
    ("GET", "/workspaces/{ws}/channels/{ch}", None),
    ("DELETE", "/workspaces/{ws}/channels/{ch}", None),
    ("GET", "/workspaces/{ws}/channels/{ch}/messages", None),
    ("POST", "/workspaces/{ws}/channels/{ch}/messages", {"body": "intruder"}),
]


@pytest.mark.parametrize("method,template,body", ENDPOINTS)
def test_outsider_gets_404_on_every_endpoint_and_changes_nothing(
    app, client, tenants, method, template, body
):
    # Bob owns Beta but has no relationship to Alpha.
    path = template.format(ws=tenants.a, ch=tenants.ch_a)
    r = client.open(path, method=method, json=body, headers=tenants.bob.headers)
    assert r.status_code == 404

    with app.app_context():
        count = lambda m: db.session.scalar(select(func.count()).select_from(m))
        assert count(Workspace) == 2
        assert count(Channel) == 2
        assert count(Message) == 2
        assert count(Membership) == 4  


def test_an_id_from_another_workspace_is_404_even_for_a_member_of_both(
    app, client, tenants
):
    """multi is an admin in both workspaces and has the right role in each.
    The workspace in the URL is authorized, but the object belongs elsewhere."""
    h = tenants.multi.headers
    wrong = f"/workspaces/{tenants.b}/channels/{tenants.ch_a}"  

    assert client.get(wrong, headers=h).status_code == 404
    assert client.get(f"{wrong}/messages", headers=h).status_code == 404
    r = client.post(f"{wrong}/messages", json={"body": "smuggled"}, headers=h)
    assert r.status_code == 404
    assert client.delete(wrong, headers=h).status_code == 404

    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Channel)) == 2
        assert db.session.scalar(select(func.count()).select_from(Message)) == 2


def test_each_workspace_lists_only_its_own_channels(client, tenants):
    h = tenants.multi.headers
    names_a = [c["name"] for c in client.get(f"/workspaces/{tenants.a}/channels", headers=h).get_json()]
    names_b = [c["name"] for c in client.get(f"/workspaces/{tenants.b}/channels", headers=h).get_json()]
    assert names_a == ["alpha-general"]
    assert names_b == ["beta-general"]


def test_responses_never_leak_the_other_tenants_data(client, tenants):
    h = tenants.multi.headers
    markers = {
        tenants.a: (SECRET_A, "alpha-general", "alice@test.dev"),
        tenants.b: (SECRET_B, "beta-general", "bob@test.dev"),
    }
    channels = {tenants.a: tenants.ch_a, tenants.b: tenants.ch_b}

    for ws, ch in channels.items():
        other = markers[tenants.b if ws == tenants.a else tenants.a]
        for path in [
            f"/workspaces/{ws}",
            f"/workspaces/{ws}/members",
            f"/workspaces/{ws}/channels",
            f"/workspaces/{ws}/channels/{ch}",
            f"/workspaces/{ws}/channels/{ch}/messages",
        ]:
            r = client.get(path, headers=h)
            assert r.status_code == 200
            text = r.get_data(as_text=True)
            for marker in other:
                assert marker not in text, f"{marker!r} leaked via {path}"

    # Control: the check can actually detect data when it's supposed to be there.
    own = client.get(f"/workspaces/{tenants.a}/channels/{tenants.ch_a}/messages", headers=h)
    assert SECRET_A in own.get_data(as_text=True)


def test_database_rejects_a_message_whose_workspace_does_not_match_its_channel(app, tenants):
    """Second layer: even if application code were wrong, Postgres refuses."""
    with app.app_context():
        db.session.add(
            Message(
                workspace_id=uuid.UUID(tenants.b),     
                channel_id=uuid.UUID(tenants.ch_a),     
                user_id=tenants.bob.id,
                body="cross-tenant write",
                seq=99,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_get_in_workspace_rejects_ids_from_other_workspaces(app, tenants):
    with app.app_context():
        with pytest.raises(NotFound):
            get_in_workspace(Channel, uuid.UUID(tenants.b), uuid.UUID(tenants.ch_a))
        # And it does work for the right pair:
        assert get_in_workspace(Channel, uuid.UUID(tenants.a), uuid.UUID(tenants.ch_a))


def test_scoped_select_refuses_models_that_are_not_tenant_data():
    with pytest.raises(TypeError):
        scoped_select(User, uuid.uuid4())