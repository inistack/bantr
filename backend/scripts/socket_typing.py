"""DEV ONLY: join a channel, then send user.typing several times quickly.

Usage: python -m scripts.socket_typing TOKEN WORKSPACE_ID CHANNEL_ID
"""
import os
import sys

import socketio

if len(sys.argv) != 4 or not all(sys.argv[1:]):
    sys.exit("usage: python -m scripts.socket_typing TOKEN WORKSPACE_ID CHANNEL_ID")
token, workspace_id, channel_id = sys.argv[1:]

URL = os.environ.get("BANTR_URL", "http://localhost:5000")
sio = socketio.Client()
sio.connect(URL, auth={"token": token}, transports=["websocket"], wait_timeout=10)

payload = {"workspace_id": workspace_id, "channel_id": channel_id}
print("join   ->", sio.call("channel.join", payload, timeout=5))
for i in range(5):
    print(f"typing {i} ->", sio.call("user.typing", payload, timeout=5))
    sio.sleep(0.2)
sio.sleep(1.2)
print("after a pause ->", sio.call("user.typing", payload, timeout=5))
sio.disconnect()