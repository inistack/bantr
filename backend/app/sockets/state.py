import time
import uuid

# Per-process state. A connection lives on exactly one process, so plain
# dicts are correct here. State that spans processes (presence) goes in Redis.
connected_users: dict[str, uuid.UUID] = {}
_typing_last: dict[str, dict[str, float]] = {}
connection_workspaces: dict[str, list[str]] = {}


def allow_typing(sid: str, room: str, min_interval: float = 1.0) -> bool:
    now = time.monotonic()
    per_connection = _typing_last.setdefault(sid, {})
    if now - per_connection.get(room, float("-inf")) < min_interval:
        return False
    per_connection[room] = now
    return True


def forget(sid: str) -> None:
    _typing_last.pop(sid, None)