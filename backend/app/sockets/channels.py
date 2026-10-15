import uuid

from flask import request
from flask_socketio import emit, join_room, leave_room

from app.errors import AppError, BadRequest, NotFound
from app.extensions import db, socketio
from app.models import User
from app.services import channel_service
from app.services.workspace_service import get_membership
from app.sockets import events
from app.sockets.connection import connected_users
from app.sockets.rooms import room_name


def _authorize(data):
    try: 
        workspace_id = uuid.UUID(str(data['workspace_id']))
        channel_id = uuid.UUID(str(data['channel_id']))
    except (KeyError, TypeError, ValueError):
        raise BadRequest('workspace_id and channel_id are required')
    
    user_id = connected_users.get(request.sid)
    if user_id is None or get_membership(user_id, workspace_id) is None:
        raise NotFound('Channel not found')
    
    channel = channel_service.get_channel(workspace_id, channel_id)
    return user_id, workspace_id, channel


def _user_payload(user_id, channel_id):
    user = db.session.get(User, user_id)
    return {
        'channel_id': str(channel_id),
        'user': {
            'id': str(user.id),
            'name': user.name,
        }
    }


@socketio.on('channel.join')
def on_join(data=None):
    try:
        user_id, workspace_id, channel = _authorize(data)
    except AppError as err:
        return {'ok': False, 'error': err.message}
    
    room = room_name(workspace_id, channel.id)
    join_room(room)

    emit(events.USER_JOINED, _user_payload(user_id, channel.id), to=room, include_self=False)
    return {'ok': True, 'last_seq': channel.last_seq}


@socketio.on('channel.leave')
def on_leave(data=None):
    try:
        user_id, workspace_id, channel = _authorize(data)
    except AppError as err:
        return {'ok': False, 'error': err.message}
    
    room = room_name(workspace_id, channel.id)
    leave_room(room)

    emit(events.USER_LEFT, _user_payload(user_id, channel.id), to=room, include_self=False)
    return {'ok': True}

