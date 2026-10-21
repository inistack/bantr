import uuid

from flask import request
from flask_socketio import emit, join_room, leave_room, rooms

from app.errors import AppError, BadRequest, NotFound
from app.extensions import db, socketio
from app.models import User
from app.services import channel_service
from app.services.workspace_service import get_membership
from app.sockets import events
from app.sockets.rooms import room_name
from app.sockets.state import allow_typing, connected_users
from app.serializers import message_to_dict
from app.services import message_service


def _parse_ids(data):
    try:
        return uuid.UUID(str(data["workspace_id"])), uuid.UUID(str(data["channel_id"]))
    except (KeyError, TypeError, ValueError):
        raise BadRequest("workspace_id and channel_id are required")


def _parse_after(data):
    after = data.get("after_seq")
    if after is None:
        return None
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise BadRequest("after_seq must be a non-negative integer")
    return after


def _authorize(data):
    """Check payload, membership, and that the channel is in THIS workspace.
    Returns (user_id, workspace_id, channel). Raises AppError otherwise."""
    workspace_id, channel_id = _parse_ids(data)
    user_id = connected_users.get(request.sid)
    if user_id is None or get_membership(user_id, workspace_id) is None:
        raise NotFound("Channel not found")
    channel = channel_service.get_channel(workspace_id, channel_id)
    return user_id, workspace_id, channel


def _user_payload(user_id, channel_id):
    user = db.session.get(User, user_id)
    return {
        "channel_id": str(channel_id),
        "user": {"id": str(user.id), "name": user.name},
    }


@socketio.on("channel.join")
def on_join(data=None):
    try:
        user_id, workspace_id, channel = _authorize(data)
        after = _parse_after(data)
    except AppError as err:
        return {"ok": False, "error": err.message}

    room = room_name(workspace_id, channel.id)
    join_room(room)
    emit(
        events.USER_JOINED,
        _user_payload(user_id, channel.id),
        to=room,
        include_self=False,
    )

    ack = {"ok": True, "last_seq": channel.last_seq}
    if after is not None:
        missed = message_service.list_messages(
            workspace_id, channel.id, after=after, limit=message_service.MAX_LIMIT
        )
        ack["missed"] = [message_to_dict(m) for m in missed]
        ack["has_more"] = len(missed) == message_service.MAX_LIMIT
    return ack


@socketio.on("channel.leave")
def on_leave(data=None):
    try:
        user_id, workspace_id, channel = _authorize(data)
    except AppError as err:
        return {"ok": False, "error": err.message}

    room = room_name(workspace_id, channel.id)
    leave_room(room)
    emit(
        events.USER_LEFT,
        _user_payload(user_id, channel.id),
        to=room,
        include_self=False,
    )
    return {"ok": True}


@socketio.on(events.USER_TYPING)
def on_typing(data=None):
    try:
        workspace_id, channel_id = _parse_ids(data)
    except AppError as err:
        return {"ok": False, "error": err.message}

    user_id = connected_users.get(request.sid)
    room = room_name(workspace_id, channel_id)
    # Having joined the room is the authorization: it was checked at join time.
    if user_id is None or room not in rooms():
        return {"ok": False, "error": "Channel not found"}
    if not allow_typing(request.sid, room):
        return {"ok": True, "throttled": True}

    emit(
        events.USER_TYPING,
        {"channel_id": str(channel_id), "user_id": str(user_id)},
        to=room,
        include_self=False,
    )
    return {"ok": True}
