import uuid
import structlog

import jwt
from flask import current_app, request
from flask_socketio import ConnectionRefusedError, emit

from app.auth.decorators import COOKIE_NAME
from app.auth.tokens import decode_token
from app.extensions import db, socketio
from app.models import User
from app.sockets.state import connected_users, forget
from app.sockets import presence as socket_presence


log = structlog.get_logger(__name__)


def _extract_token(auth) -> str | None:
    if isinstance(auth, dict) and auth.get("token"):
        return auth["token"]
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return request.cookies.get(COOKIE_NAME)


@socketio.on("connect")
def on_connect(auth):
    token = _extract_token(auth)
    if not token:
        raise ConnectionRefusedError("authentication required")
    try:
        claims = decode_token(token)
        user = db.session.get(User, uuid.UUID(claims["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        raise ConnectionRefusedError("invalid token")
    if user is None:
        raise ConnectionRefusedError("invalid token")

    connected_users[request.sid] = user.id
    socket_presence.on_connect(request.sid, user.id)
    log.info("socket.connected", sid=request.sid, user_id=str(user.id))
    emit("connected", {"user_id": str(user.id)})


@socketio.on("disconnect")
def on_disconnect(*args):
    user_id = connected_users.pop(request.sid, None)
    forget(request.sid)
    if user_id is not None:
        socket_presence.on_disconnect(request.sid, user_id)
    log.info("socket.disconnected", sid=request.sid, user_id=str(user_id) if user_id else None)


@socketio.on("whoami")
def on_whoami():
    return {"user_id": str(connected_users[request.sid])}