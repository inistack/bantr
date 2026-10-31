import contextlib
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests
import socketio

from tests.helpers import add_member, create_channel, create_ws

BACKEND_DIR = Path(__file__).resolve().parents[2]


# ---- helpers -------------------------------------------------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, port, env, logfile):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.logfile = logfile
        self._log = open(logfile, "w")
        self.proc = subprocess.Popen(
            [sys.executable, "wsgi.py"],
            cwd=BACKEND_DIR, env=env, stdout=self._log, stderr=subprocess.STDOUT,
        )

    def log_tail(self, lines=25):
        self._log.flush()
        return "\n".join(Path(self.logfile).read_text().splitlines()[-lines:])

    def wait_ready(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"server on port {self.port} exited early:\n{self.log_tail()}")
            try:
                if requests.get(f"{self.url}/health", timeout=1).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.2)
        raise RuntimeError(f"server on port {self.port} never became ready:\n{self.log_tail()}")

    def kill(self):
        """SIGKILL: no shutdown handlers run, like a crash."""
        self.proc.kill()
        self.proc.wait(timeout=5)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self._log.close()


@contextlib.contextmanager
def server_pair(redis_url, tmp_path, **extra_env):
    """Two server processes sharing one Redis and one Socket.IO channel."""
    base = {
        **os.environ,
        "APP_ENV": "e2e",
        "APP_DEBUG": "0",
        "TEST_REDIS_URL": redis_url,
        "SOCKETIO_CHANNEL": f"bantr-e2e-{uuid.uuid4().hex[:8]}",
        **extra_env,
    }
    ports = []
    while len(ports) < 2:
        port = free_port()
        if port not in ports:
            ports.append(port)
    servers = [
        Server(port, {**base, "PORT": str(port)}, tmp_path / f"server-{port}.log")
        for port in ports
    ]
    try:
        for server in servers:
            server.wait_ready()
        yield servers
    finally:
        for server in servers:
            server.stop()


class Listener:
    """A real Socket.IO client that records every event it receives."""

    def __init__(self, server, user, reconnect=True):
        self.events = []
        self.sio = socketio.Client(reconnection=reconnect)
        for name in ("message.sent", "user.joined", "user.typing", "presence.update"):
            self.sio.on(name, lambda data, name=name: self.events.append((name, data)))
        token = user.headers["Authorization"].split(" ", 1)[1]
        self.sio.connect(server.url, auth={"token": token}, transports=["websocket"], wait_timeout=10)

    def received(self, name):
        return [data for event, data in self.events if event == name]

    def join(self, ws, ch):
        ack = self.sio.call("channel.join", {"workspace_id": ws, "channel_id": ch}, timeout=10)
        assert ack["ok"], ack

    def typing(self, ws, ch):
        return self.sio.call("user.typing", {"workspace_id": ws, "channel_id": ch}, timeout=10)

    def presence_list(self, ws):
        return self.sio.call("presence.list", {"workspace_id": ws}, timeout=10)

    def close(self):
        if self.sio.connected:
            self.sio.disconnect()


def wait_for(predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def send_via(server, user, ws, ch, body):
    return requests.post(
        f"{server.url}/workspaces/{ws}/channels/{ch}/messages",
        json={"body": body}, headers=user.headers, timeout=10,
    )


def read_via(server, user, ws, ch):
    r = requests.get(f"{server.url}/workspaces/{ws}/channels/{ch}/messages", headers=user.headers, timeout=10)
    assert r.status_code == 200
    return r.json()


def metric(server, prefix):
    for line in requests.get(f"{server.url}/metrics", timeout=5).text.splitlines():
        if line.startswith(prefix):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def is_presence(user, ws, online):
    return lambda e: e["user_id"] == str(user.id) and e["workspace_id"] == ws and e["online"] is online


def setup(client, make_user):
    owner, bob = make_user("owner@test.dev"), make_user("bob@test.dev")
    ws = create_ws(client, owner)
    ch = create_channel(client, owner, ws)
    add_member(client, owner, ws, "bob@test.dev")
    return owner, bob, ws, ch


# ---- tests ---------------------------------------------------------------------------

def test_a_message_sent_to_one_server_reaches_a_client_on_the_other(
    client, make_user, real_redis, real_redis_url, tmp_path
):
    owner, bob, ws, ch = setup(client, make_user)
    with server_pair(real_redis_url, tmp_path) as (a, b):
        listener = Listener(b, owner)
        try:
            listener.join(ws, ch)
            assert send_via(a, bob, ws, ch, "across servers").status_code == 201
            assert wait_for(lambda: listener.received("message.sent"))
            message = listener.received("message.sent")[0]["message"]
            assert message["body"] == "across servers" and message["seq"] == 1
        finally:
            listener.close()


def test_joins_and_typing_cross_servers(client, make_user, real_redis, real_redis_url, tmp_path):
    owner, bob, ws, ch = setup(client, make_user)
    with server_pair(real_redis_url, tmp_path) as (a, b):
        on_b, on_a = Listener(b, owner), Listener(a, bob)
        try:
            on_b.join(ws, ch)
            on_a.join(ws, ch)
            assert wait_for(lambda: on_b.received("user.joined"))
            assert on_b.received("user.joined")[0]["user"]["id"] == str(bob.id)
            assert on_a.typing(ws, ch) == {"ok": True}
            assert wait_for(lambda: on_b.received("user.typing"))
            assert on_b.received("user.typing")[0]["user_id"] == str(bob.id)
        finally:
            on_b.close()
            on_a.close()


def test_presence_is_shared_between_servers(client, make_user, real_redis, real_redis_url, tmp_path):
    owner, bob, ws, ch = setup(client, make_user)
    with server_pair(real_redis_url, tmp_path) as (a, b):
        on_b = Listener(b, owner)
        on_a = Listener(a, bob)
        try:
            assert wait_for(lambda: any(map(is_presence(bob, ws, True), on_b.received("presence.update"))))
            ack = on_b.presence_list(ws)
            assert ack["ok"] and set(ack["online"]) == {str(owner.id), str(bob.id)}
            on_a.close()
            assert wait_for(lambda: any(map(is_presence(bob, ws, False), on_b.received("presence.update"))))
            assert on_b.presence_list(ws)["online"] == [str(owner.id)]
        finally:
            on_b.close()
            on_a.close()


def test_a_crashed_server_is_noticed_and_its_users_are_announced_offline(
    client, make_user, real_redis, real_redis_url, tmp_path
):
    owner, bob, ws, ch = setup(client, make_user)
    with server_pair(real_redis_url, tmp_path) as (a, b):
        on_b = Listener(b, owner)
        on_a = Listener(a, bob, reconnect=False)
        try:
            assert wait_for(lambda: any(map(is_presence(bob, ws, True), on_b.received("presence.update"))))
            a.kill()  # no disconnect handler runs: only the heartbeat expiry can notice
            assert wait_for(
                lambda: any(map(is_presence(bob, ws, False), on_b.received("presence.update"))),
                timeout=20,
            )
            assert on_b.presence_list(ws)["online"] == [str(owner.id)]
        finally:
            on_b.close()
            on_a.close()


def test_the_rate_limit_is_shared_between_servers(client, make_user, real_redis, real_redis_url, tmp_path):
    owner, bob, ws, ch = setup(client, make_user)
    with server_pair(real_redis_url, tmp_path, E2E_MESSAGE_RATE_LIMIT="3 per minute") as (a, b):
        statuses = [send_via(server, owner, ws, ch, f"m{i}").status_code for i, server in enumerate([a, b, a, b])]
        assert statuses == [201, 201, 201, 429]  # neither server alone saw more than two


def test_the_message_cache_is_shared_and_kept_current_across_servers(
    client, make_user, real_redis, real_redis_url, tmp_path
):
    owner, bob, ws, ch = setup(client, make_user)
    hit = 'bantr_message_cache_requests_total{result="hit"}'
    miss = 'bantr_message_cache_requests_total{result="miss"}'
    with server_pair(real_redis_url, tmp_path) as (a, b):
        assert send_via(a, owner, ws, ch, "m0").status_code == 201   # no cache yet: nothing to update
        assert [m["body"] for m in read_via(b, owner, ws, ch)] == ["m0"]   # miss: B fills the cache
        assert send_via(a, owner, ws, ch, "m1").status_code == 201   # A updates B's cache through Redis
        assert real_redis.zcard(f"msgs:ws:{ws}:ch:{ch}") == 2
        assert [m["body"] for m in read_via(b, owner, ws, ch)] == ["m0", "m1"]   # hit
        assert (metric(b, hit), metric(b, miss)) == (1.0, 1.0)