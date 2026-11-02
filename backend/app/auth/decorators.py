import uuid
from functools import wraps

import jwt
from flask import g, jsonify, request
from sqlalchemy import select

from app.auth.tokens import decode_token
from app.errors import Forbidden, NotFound
from app.extensions import db
from app.models import ROLE_RANK, Membership, User

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


def require_role(minimum):
    def decorator(fn):
        @wraps(fn)
        def wrapper(workspace_id, *args, **kwargs):
            membership = db.session.scalar(
                select(Membership).where(
                    Membership.user_id == g.current_user.id,
                    Membership.workspace_id == workspace_id
                )
            )
            if membership is None:
                raise NotFound('Workspace not found')
            if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
                raise Forbidden('Insufficient role')
            g.membership = membership
            return fn(workspace_id, *args, **kwargs)
        return login_required(wrapper)
    return decorator