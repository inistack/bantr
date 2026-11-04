from datetime import UTC, datetime, timedelta

import jwt

from app.extensions import db, socketio
from app.models import User


def token_of(user):
    return user.headers["Authorization"].split(" ", 1)[1]


def test_connecting_without_a_token_is_refused(app):
    assert not socketio.test_client(app).is_connected()


def test_a_garbage_token_is_refused(app):
    assert not socketio.test_client(app, auth={"token": "not.a.token"}).is_connected()


def test_an_expired_token_is_refused(app, make_user):
    user = make_user("a@test.dev")
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(minutes=1)},
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    assert not socketio.test_client(app, auth={"token": expired}).is_connected()


def test_a_token_for_a_deleted_user_is_refused(app, make_user):
    user = make_user("a@test.dev")
    with app.app_context():
        db.session.delete(db.session.get(User, user.id))
        db.session.commit()
    assert not socketio.test_client(app, auth={"token": token_of(user)}).is_connected()


def test_a_bearer_header_is_accepted(app, make_user):
    user = make_user("a@test.dev")
    headers = {"Authorization": f"Bearer {token_of(user)}"}
    assert socketio.test_client(app, headers=headers).is_connected()


def test_the_httponly_cookie_is_accepted(app, client, make_user):
    user = make_user("a@test.dev")
    client.set_cookie("bantr_token", token_of(user))
    assert socketio.test_client(app, flask_test_client=client).is_connected()