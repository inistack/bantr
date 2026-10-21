"""DEV ONLY: a client that survives drops and gaps.

Usage: python -m scripts.resume_client TOKEN WORKSPACE_ID CHANNEL_ID
"""
import os
import sys
import threading

import requests
import socketio

if len(sys.argv) != 4 or not all(sys.argv[1:]):
    sys.exit("usage: python -m scripts.resume_client TOKEN WORKSPACE_ID CHANNEL_ID")
token, WS, CH = sys.argv[1:]

URL = os.environ.get("BANTR_URL", "http://localhost:5000")
HTTP = os.environ.get("BANTR_HTTP_URL", URL)  # history can be read from any server

lock = threading.RLock()
last = None  # highest seq this client has applied
sio = socketio.Client()  # reconnects automatically


def show(m, how):
    print(f"[{how}] seq={m['seq']} {m['user']['name']}: {m['body']}")


def fetch_after(seq):
    r = requests.get(
        f"{HTTP}/workspaces/{WS}/channels/{CH}/messages",
        params={"after": seq, "limit": 100},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def apply_in_order(messages, how):
    global last
    for m in messages:
        if m["seq"] > last:  # ignore duplicates
            show(m, how)
            last = m["seq"]


def catch_up(how):
    while True:
        batch = fetch_after(last)
        apply_in_order(batch, how)
        if len(batch) < 100:
            return


@sio.on("message.sent")
def on_live(data):
    global last
    m = data["message"]
    with lock:
        if last is None or m["seq"] <= last:
            return
        if m["seq"] == last + 1:
            show(m, "live")
            last = m["seq"]
        else:
            print(f"[gap] expected seq {last + 1}, got {m['seq']}: fetching the missing ones")
            catch_up("gap")


def resume():
    global last
    with lock:  # live events wait here until the join finishes
        payload = {"workspace_id": WS, "channel_id": CH}
        if last is not None:
            payload["after_seq"] = last
        ack = sio.call("channel.join", payload, timeout=10)
        if not ack.get("ok"):
            print("join refused:", ack)
            return
        if last is None:
            last = ack["last_seq"]
            print(f"joined, starting after seq {last}")
            return
        apply_in_order(ack["missed"], "resume")
        if ack["has_more"]:
            catch_up("resume")
        print(f"resumed, now at seq {last}")


@sio.event
def connect():
    print("connected")
    # Don't block inside the connect handler: the join's ack arrives on this same thread.
    sio.start_background_task(resume)


@sio.event
def disconnect():
    print("disconnected (will retry)")


sio.connect(URL, auth={"token": token}, transports=["websocket"], wait_timeout=10)
print("running... Ctrl+C to stop")
try:
    sio.wait()
except KeyboardInterrupt:
    sio.disconnect()