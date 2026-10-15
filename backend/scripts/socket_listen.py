"""DEV ONLY: join a channel room and print every event received.

Usage: python -m scripts.socket_listen TOKEN WORKSPACE_ID CHANNEL_ID
"""
import sys
import os
import socketio

URL = os.environ.get("BANTR_URL", "http://localhost:5000")


token, workspace_id, channel_id = sys.argv[1:4]
sio = socketio.Client()

for name in ("connected", "message.sent", "user.joined", "user.left"):
    sio.on(name, lambda data, name=name: print(f"<- {name}: {data}"))

sio.connect(
    URL,
    auth={"token": token},
    transports=["websocket"],
    wait_timeout=10,
)
print("join ->", sio.call("channel.join", {"workspace_id": workspace_id, "channel_id": channel_id}, timeout=5))
print("listening... (Ctrl+C to stop)")
try:
    sio.wait()
except KeyboardInterrupt:
    sio.disconnect()