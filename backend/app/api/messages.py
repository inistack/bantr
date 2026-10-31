from flask import Blueprint, g, jsonify, request, current_app

from app.auth.decorators import require_role
from app.errors import BadRequest
from app.models import Role
from app.services import message_service as svc
from app.extensions import socketio
from app.sockets import events
from app.sockets.rooms import room_name
from app.serializers import message_to_dict as _json
from app.rate_limit import limiter, rate_limit_key
import structlog
from app import metrics


log = structlog.get_logger(__name__)
message_bp = Blueprint('message', __name__, url_prefix='/workspaces/<uuid:workspace_id>/channels/<uuid:channel_id>/messages')


def _int_arg(name):
    raw = request.args.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        raise BadRequest(f'{name} must be an integer')
    

@message_bp.post('')
@limiter.limit(lambda: current_app.config["MESSAGE_RATE_LIMIT"], key_func=rate_limit_key)
@require_role(Role.MEMBER)
def send(workspace_id, channel_id):
    data = request.get_json(silent=True) or {}
    body = (data.get('body') or '').strip()
    if not body:
        raise BadRequest('body is required')
    if len(body) > svc.MAX_BODY:
        raise BadRequest(f'body must be at most {svc.MAX_BODY} characters')
    message = svc.send_message(workspace_id, channel_id, g.current_user, body)
    payload = _json(message)
    log.info(
        "message.sent",
        workspace_id=str(workspace_id),
        channel_id=str(channel_id),
        seq=message.seq,
        user_id=str(g.current_user.id),
    )
    metrics.MESSAGES_SENT.inc()
    svc.cache_new_message(workspace_id, channel_id, payload)

    try:
        socketio.emit(
            events.MESSAGE_SENT,
            {"channel_id": str(channel_id), "message": payload},
            to=room_name(workspace_id, channel_id),
        )
    except Exception:
        log.exception("broadcast.failed", event_name="message.sent")

    return jsonify(payload), 201


@message_bp.get('')
@require_role(Role.MEMBER)
def history(workspace_id, channel_id):
    limit = _int_arg("limit") or 50
    after, before = _int_arg("after"), _int_arg("before")
    if after is None and before is None:
        return jsonify(svc.recent_messages(workspace_id, channel_id, limit))
    rows = svc.list_messages(
        workspace_id, channel_id, after=after, before=before, limit=limit
    )
    return jsonify([_json(m) for m in rows])