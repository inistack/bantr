import uuid
from functools import wraps
from flask import g, request, jsonify
from app.models import User
from app.auth.tokens import decode_token
from app.extensions import db
import jwt

COOKIE_NAME = 'bantr_token'

def _extract_token():
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        return header[len('Bearer '):]
    return request.cookies.get(COOKIE_NAME)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify(error='Authentication required'), 401
        try:
            claims = decode_token(token)
            user = db.session.get(User, uuid.UUID(claims['sub']))
        except (jwt.InvalidTokenError, ValueError):
            return jsonify(error='Invalid or expired token'), 401
        if user is None:
            return jsonify(error='Invalid or expired token'), 401
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper

