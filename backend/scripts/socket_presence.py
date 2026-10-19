"""DEV ONLY: print who is online in a workspace, then stay and print updates.

Usage: python -m scripts.socket_presence TOKEN WORKSPACE_ID
"""
import os
import sys

import socketio

if len(sys.argv) != 3 or not all(sys.argv[1:]):
    sys.exit("usage: python -m scripts.socket_presence TOKEN WORKSPACE_ID")
token, workspace_id = sys.argv[1:]

URL = os.environ.get("BANTR_URL", "http://localhost:5000")
sio = socketio.Client()
sio.on("presence.update", lambda data: print("<- presence.update:", data))
sio.connect(URL, auth={"token": token}, transports=["websocket"], wait_timeout=10)
print("online ->", sio.call("presence.list", {"workspace_id": workspace_id}, timeout=5))
print("listening... (Ctrl+C to stop)")
try:
    sio.wait()
except KeyboardInterrupt:
    sio.disconnect()