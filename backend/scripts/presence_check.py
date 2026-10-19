"""DEV ONLY: end-to-end presence check across two server processes.

Needs OWNER, BOB and ALPHA in the environment (source scripts/dev_env.sh),
a server on port 5000 and another on port 5001.
"""
import os
import sys
import time

import jwt
import socketio

OWNER, BOB, WS = os.environ["OWNER"], os.environ["BOB"], os.environ["ALPHA"]
URL_BOB = os.environ.get("BANTR_URL_A", "http://localhost:5000")
URL_OWNER = os.environ.get("BANTR_URL_B", "http://localhost:5001")

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print("PASS" if ok else "FAIL", "-", name, detail)


def connect(url, token):
    events = []
    sio = socketio.Client()
    sio.on("presence.update", lambda d: events.append((time.time(), d)))
    sio.connect(url, auth={"token": token}, transports=["websocket"], wait_timeout=10)
    return sio, events


def about(events, user_id, online=None):
    return [
        (ts, d) for ts, d in events
        if d["workspace_id"] == WS and d["user_id"] == user_id
        and (online is None or d["online"] == online)
    ]


def wait_for(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return pred()


bob_id = jwt.decode(BOB, options={"verify_signature": False})["sub"]

owner, ev_owner = connect(URL_OWNER, OWNER)
owner_id = owner.call("whoami", timeout=5)["user_id"]
before = owner.call("presence.list", {"workspace_id": WS}, timeout=5)["online"]
print("online before Bob connects:", before)
check("Bob is not shown online before he connects (no ghost entries)", bob_id not in before)

bob, ev_bob = connect(URL_BOB, BOB)
t_connect = time.time()
arrived = wait_for(lambda: about(ev_owner, bob_id, True), 5)
latency = f"({about(ev_owner, bob_id, True)[0][0] - t_connect:.2f}s)" if arrived else ""
check("Bob's arrival was announced to the owner on the other server", arrived, latency)

print("waiting 25s (two heartbeats) ...")
time.sleep(25)
check("Bob never received a presence.update about himself", not about(ev_bob, bob_id))
check(
    "owner saw exactly one 'online' and no 'offline' for Bob while he stayed connected",
    len(about(ev_owner, bob_id, True)) == 1 and not about(ev_owner, bob_id, False),
)

t_leave = time.time()
bob.disconnect()
left = wait_for(lambda: about(ev_owner, bob_id, False), 5)
latency = f"({about(ev_owner, bob_id, False)[0][0] - t_leave:.2f}s)" if left else ""
check("Bob's clean disconnect was announced within 5s", left, latency)

final = owner.call("presence.list", {"workspace_id": WS}, timeout=5)["online"]
check("final presence list contains only the owner", final == [owner_id], str(final))

owner.disconnect()
print("ALL CHECKS PASSED" if all(results) else "SOME CHECKS FAILED")
sys.exit(0 if all(results) else 1)