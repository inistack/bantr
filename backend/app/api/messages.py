from flask import Blueprint, g, jsonify, request

from app.auth.decorators import require_role
from app.errors import BadRequest
from app.models import Role
from app.services import message_service as svc

message_bp = Blueprint('message', __name__, url_prefix='/workspaces/<uuid:workspace_id>/channels/<uuid:channel_id>/messages')

def _json(m):
    return {
        "id": str(m.id),
        "seq": m.seq,
        "body": m.body,
        "created_at": m.created_at.isoformat(),
        "user": {
            "id": str(m.user.id),
            "name": m.user.name,
            "avatar_url": m.user.avatar_url,
        },
    }

def _int_arg(name):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        raise BadRequest(f'{name} must be an integer')
    

@message_bp.post('')
@require_role(Role.MEMBER)
def send(workspace_id, channel_id):
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body:
        raise BadRequest('body is required')
    if len(body) > svc.MAX_BODY:
        raise BadRequest(f'body must be at most {svc.MAX_BODY} characters')
    message = svc.send_message(workspace_id, channel_id, g.current_user, body)
    return jsonify(_json(message)), 201


@message_bp.get('')
@require_role(Role.MEMBER)
def history(workspace_id, channel_id):
    limit = _int_arg('limit') or 50
    rows = svc.list_messages(
        workspace_id, channel_id, after=_int_arg('after'), before=_int_arg('before'), limit=limit
    )
    return jsonify([_json(m) for m in rows])