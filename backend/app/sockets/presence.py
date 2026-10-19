import threading
import time
import uuid

import redis
from flask import current_app, request
from flask_socketio import join_room

from app.extensions import socketio
from app.redis_client import get_redis
from app.services import presence_service
from app.services.workspace_service import get_membership, workspace_ids_for_user
from app.sockets import events
from app.sockets.rooms import workspace_room
from app.sockets.state import connected_users, connection_workspaces

_started = False
_start_lock = threading.Lock()


def _ttl() -> int:
    return current_app.config["PRESENCE_TTL_SECONDS"]


def announce(workspace_id, user_id, online, source, skip_sid=None):
    current_app.logger.info(
        "presence.announce source=%s ws=%s user=%s online=%s skip_sid=%s",
        source, workspace_id, user_id, online, skip_sid,
    )
    socketio.emit(
        events.PRESENCE_UPDATE,
        {"workspace_id": str(workspace_id), "user_id": str(user_id), "online": online},
        to=workspace_room(workspace_id),
        skip_sid=skip_sid,
    )


def on_connect(sid, user_id):
    ids = [str(w) for w in workspace_ids_for_user(user_id)]
    connection_workspaces[sid] = ids
    for ws in ids:
        join_room(workspace_room(ws))

    r = get_redis()
    if r is None:
        return
    _ensure_heartbeat_running(current_app._get_current_object())
    try:
        for ws in presence_service.add_connection(r, ids, str(user_id), sid, time.time(), _ttl()):
            announce(ws, user_id, True, "connect", skip_sid=sid)
    except redis.RedisError:
        # Never refuse a connection because presence is down; the heartbeat
        # re-registers it and announces once Redis is back.
        current_app.logger.exception("presence: could not register connection")


def on_disconnect(sid, user_id):
    ids = connection_workspaces.pop(sid, [])
    r = get_redis()
    if r is None:
        return
    try:
        for ws in presence_service.remove_connection(r, ids, str(user_id), sid, time.time(), _ttl()):
            announce(ws, user_id, False, "disconnect") 
    except redis.RedisError:
        current_app.logger.exception("presence: could not unregister connection")


@socketio.on("presence.list")
def on_presence_list(data=None):
    try:
        workspace_id = uuid.UUID(str(data["workspace_id"]))
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "error": "workspace_id is required"}

    user_id = connected_users.get(request.sid)
    if user_id is None or get_membership(user_id, workspace_id) is None:
        return {"ok": False, "error": "Workspace not found"}

    r = get_redis()
    if r is None:
        return {"ok": False, "error": "Presence unavailable"}
    try:
        online = presence_service.online_user_ids(r, str(workspace_id), time.time(), _ttl())
    except redis.RedisError:
        return {"ok": False, "error": "Presence unavailable"}
    return {"ok": True, "online": online}


def run_heartbeat_once():
    """Refresh this process's connections, then reap dead ones in the workspaces we serve."""
    r = get_redis()
    if r is None:
        return
    now, ttl = time.time(), _ttl()
    snapshot = list(connection_workspaces.items())  # copy: handlers mutate it concurrently

    entries = []
    for sid, ids in snapshot:
        user_id = connected_users.get(sid)
        if user_id is not None:
            entries.append((ids, str(user_id), sid))

    # Entries that had been reaped (or lost with a Redis restart) are re-created and re-announced.
    for ws, user_id in set(presence_service.heartbeat(r, entries, now, ttl)):
        announce(ws, user_id, True, "heartbeat-recreate")

    watched = {ws for _, ids in snapshot for ws in ids}
    for ws in watched:
        for user_id in presence_service.reap_stale(r, ws, now, ttl):
            announce(ws, user_id, False, "reaper")


def _heartbeat_loop(app):
    interval = app.config["PRESENCE_HEARTBEAT_SECONDS"]
    while True:
        socketio.sleep(interval)
        try:
            with app.app_context():
                run_heartbeat_once()
        except Exception:
            app.logger.exception("presence heartbeat failed")


def _ensure_heartbeat_running(app):
    """Start the background loop once per process, on its first connection.
    Starting it lazily keeps the dev reloader's idle parent process from running one."""
    global _started
    if app.testing:
        return
    with _start_lock:
        if not _started:
            socketio.start_background_task(_heartbeat_loop, app)
            _started = True

