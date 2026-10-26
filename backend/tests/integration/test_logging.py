import io
import json
import logging

import pytest
import structlog

from app.logging_config import configure_logging
from app.rate_limit import limiter
from tests.helpers import create_channel, create_ws, send

SECRET_BODY = "TOPSECRET-BODY-123"


def events(caplog, name=None):
    """Our structured events, from the records pytest captured."""
    found = [r.msg for r in caplog.records if isinstance(r.msg, dict)]
    return [e for e in found if name is None or e.get("event") == name]


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def test_every_response_has_a_request_id(client):
    r = client.get("/auth/me")
    assert len(r.headers["X-Request-ID"]) == 32


def test_a_safe_incoming_request_id_is_kept(client):
    r = client.get("/auth/me", headers={"X-Request-ID": "demo-123"})
    assert r.headers["X-Request-ID"] == "demo-123"


def test_an_unsafe_incoming_request_id_is_replaced(client):
    r = client.get("/auth/me", headers={"X-Request-ID": "not safe, has spaces"})
    assert r.headers["X-Request-ID"] != "not safe, has spaces"
    assert len(r.headers["X-Request-ID"]) == 32


def test_the_access_log_has_the_expected_fields(client, make_user, caplog):
    caplog.set_level(logging.INFO)
    user = make_user("a@test.dev")
    r = client.get("/auth/me", headers=user.headers)
    (entry,) = events(caplog, "http.request")
    assert entry["method"] == "GET" and entry["path"] == "/auth/me" and entry["status"] == 200
    assert entry["user_id"] == str(user.id)
    assert entry["request_id"] == r.headers["X-Request-ID"]
    assert entry["duration_ms"] >= 0


def test_events_inside_a_request_carry_its_request_id(client, make_user, caplog):
    caplog.set_level(logging.INFO)
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "hello")
    caplog.clear()
    client.get(
        f"/workspaces/{ws}/channels/{ch}/messages",
        headers={**owner.headers, "X-Request-ID": "abc-1"},
    )
    cache_events = [e for e in events(caplog) if e["event"].startswith("message_cache.")]
    assert cache_events and all(e["request_id"] == "abc-1" for e in cache_events)


def test_sending_logs_ids_and_seq_but_never_the_body_or_the_token(client, make_user, caplog):
    caplog.set_level(logging.INFO)
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, SECRET_BODY)
    (sent,) = events(caplog, "message.sent")
    assert sent["seq"] == 1 and sent["channel_id"] == ch and sent["user_id"] == str(owner.id)
    everything = " ".join(str(r.msg) + r.getMessage() for r in caplog.records)
    assert SECRET_BODY not in everything
    assert owner.headers["Authorization"].split(" ", 1)[1] not in everything


def test_a_rate_limit_rejection_is_logged(app, client, make_user, caplog, monkeypatch):
    monkeypatch.setitem(app.config, "MESSAGE_RATE_LIMIT", "1 per minute")
    limiter.reset()
    caplog.set_level(logging.INFO)
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "one")
    assert send(client, owner, ws, ch, "two").status_code == 429
    (entry,) = events(caplog, "rate_limit.exceeded")
    assert entry["key"] == f"user:{owner.id}"
    limiter.reset()


def test_json_format_emits_one_object_per_line_even_for_standard_logging():
    handler = configure_logging("json", "INFO")
    buffer = io.StringIO()
    handler.setStream(buffer)
    try:
        structlog.get_logger("demo").info("thing.happened", workspace_id="w1", count=3)
        logging.getLogger("some.library").warning("plain library message")
        first, second = [json.loads(line) for line in buffer.getvalue().strip().splitlines()]
        assert first["event"] == "thing.happened"
        assert first["workspace_id"] == "w1" and first["count"] == 3
        assert first["level"] == "info" and first["logger"] == "demo" and "timestamp" in first
        assert second["event"] == "plain library message" and second["level"] == "warning"
    finally:
        configure_logging("console", "WARNING")