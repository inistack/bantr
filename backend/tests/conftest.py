from types import SimpleNamespace

import pytest
from sqlalchemy import text
import os
import redis as redis_lib

from app import create_app
from app.auth.tokens import issue_token
from app.extensions import db
from app.models import User
import fakeredis
from app.sockets.state import connected_users, connection_workspaces


REAL_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")

@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    app.extensions["redis"] = fakeredis.FakeRedis(decode_responses=True)
    uri = app.config["SQLALCHEMY_DATABASE_URI"] or ""
    assert uri.rsplit("/", 1)[-1].endswith("_test"), f"Refusing to run tests on {uri!r}"
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def _clean_db(app):
    """After every test, empty all tables."""
    yield
    connected_users.clear()
    connection_workspaces.clear()
    app.extensions["redis"].flushall()
    with app.app_context():
        db.session.remove()
        tables = ", ".join(t.name for t in db.metadata.sorted_tables)
        db.session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Create a user and return their id, email, and ready-to-use auth headers."""

    def _make(email, name=None):
        with app.app_context():
            user = User(email=email, name=name or email.split("@")[0])
            db.session.add(user)
            db.session.commit()
            uid = user.id
            token = issue_token(uid)
        return SimpleNamespace(
            id=uid, email=email, headers={"Authorization": f"Bearer {token}"}
        )

    return _make


def real_redis_or_skip():
    client = redis_lib.Redis.from_url(REAL_REDIS_URL, decode_responses=True)
    db = client.connection_pool.connection_kwargs.get("db", 0)
    assert db != 0, "TEST_REDIS_URL must not use database 0: the tests flush their database"
    try:
        client.ping()
    except redis_lib.RedisError:
        if os.environ.get("REQUIRE_REAL_REDIS") == "1":
            pytest.fail(f"real Redis required but unreachable at {REAL_REDIS_URL}")
        pytest.skip(f"no Redis reachable at {REAL_REDIS_URL}")
    return client


@pytest.fixture(params=["fake", "real"])
def r(request):
    """A Redis client. Tests using it run once against fakeredis and once against real Redis."""
    if request.param == "fake":
        client = fakeredis.FakeRedis(decode_responses=True)
    else:
        client = real_redis_or_skip()
    client.flushdb()
    yield client
    client.flushdb()