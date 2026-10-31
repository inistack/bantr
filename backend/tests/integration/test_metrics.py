from prometheus_client import REGISTRY

from tests.helpers import create_channel, create_ws, send, socket_connect


def value(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


def setup(client, make_user):
    owner = make_user("owner@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    return owner, ws, ch


def test_metrics_endpoint_serves_prometheus_text(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.content_type.startswith("text/plain")
    body = r.get_data(as_text=True)
    assert "bantr_messages_sent_total" in body
    assert "bantr_socket_connections" in body


def test_sending_a_message_increments_the_counter(client, make_user):
    owner, ws, ch = setup(client, make_user)
    before = value("bantr_messages_sent_total")
    send(client, owner, ws, ch, "one")
    send(client, owner, ws, ch, "two")
    assert value("bantr_messages_sent_total") - before == 2


def test_cache_results_are_counted_by_label(client, make_user):
    owner, ws, ch = setup(client, make_user)
    send(client, owner, ws, ch, "one")
    url = f"/workspaces/{ws}/channels/{ch}/messages"
    labels = {"result": "hit"}, {"result": "miss"}
    hit0, miss0 = (value("bantr_message_cache_requests_total", lab) for lab in labels)
    client.get(url, headers=owner.headers)  # miss: fills the cache
    client.get(url, headers=owner.headers)  # hit
    hit1, miss1 = (value("bantr_message_cache_requests_total", lab) for lab in labels)
    assert (hit1 - hit0, miss1 - miss0) == (1, 1)


def test_http_metrics_use_the_route_template_not_the_raw_path(client, make_user):
    owner, ws, ch = setup(client, make_user)
    client.get(f"/workspaces/{ws}", headers=owner.headers)
    routes = {
        s.labels["route"]
        for family in REGISTRY.collect()
        for s in family.samples
        if "route" in s.labels
    }
    assert "/workspaces/<uuid:workspace_id>" in routes
    assert not any(ws in route or ch in route for route in routes)


def test_authenticated_requests_are_counted_with_method_route_and_status(client, make_user):
    user = make_user("a@test.dev")
    labels = {"method": "GET", "route": "/auth/me", "status": "200"}
    before = value("bantr_http_requests_total", labels)
    client.get("/auth/me", headers=user.headers)
    client.get("/auth/me", headers=user.headers)
    assert value("bantr_http_requests_total", labels) - before == 2


def test_scrapes_are_not_counted_as_traffic(client):
    for _ in range(3):
        client.get("/metrics")
    routes = {
        s.labels["route"]
        for family in REGISTRY.collect()
        for s in family.samples
        if "route" in s.labels
    }
    assert "/metrics" not in routes


def test_metrics_require_the_token_when_one_is_configured(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_the_connection_gauge_follows_connects_and_disconnects(app, make_user):
    before = value("bantr_socket_connections")
    sio_client = socket_connect(app, make_user("a@test.dev"))
    assert value("bantr_socket_connections") == before + 1
    sio_client.disconnect()
    assert value("bantr_socket_connections") == before