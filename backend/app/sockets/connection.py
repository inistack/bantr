import uuid
from flask import current_app, request
from app.auth.decorators import COOKIE_NAME
from flask_socketio import emit, ConnectionRefusedError
from app.auth.tokens import decode_token
from app.extensions import db, socketio
from app.models import User
import jwt


connected_users: dict[str, uuid.UUID] = {}

def _extract_token(auth):
    if isinstance(auth, dict) and auth.get('token'):
        return auth['token']
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[len('Bearer '):]
    return request.cookies.get(COOKIE_NAME)


@socketio.on('connect')
def on_connect(auth):
    token = _extract_token(auth)
    if not token:
        raise ConnectionRefusedError('authentication required')
    try:
        claims = decode_token(token)
        user = db.session.get(User, uuid.UUID(claims['sub']))
    except (jwt.InvalidTokenError,ValueError):
        raise ConnectionRefusedError('invalid token')
    
    if user is None:
        raise ConnectionRefusedError('invalid token')
    
    connected_users[request.sid] = user.id
    current_app.logger.info('socket connected: %s, user: %s', request.sid, user.id)
    emit('connected', {'user_id': str(user.id)})


@socketio.on('disconnect')
def on_disconnect(*args):
    user_id = connected_users.pop(request.sid, None)
    current_app.logger.info('socket disconnected: %s, user: %s', request.sid, user_id)


@socketio.on('whoami')
def on_whoami():
    return {'user_id': str(connected_users[request.sid])}


@socketio.on_error_default
def on_error(e):
    current_app.logger.exception("socket handler error: %r", e)
    raise e