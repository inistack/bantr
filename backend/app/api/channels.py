import re

from flask import Blueprint, g, jsonify, request

from app.auth.decorators import require_role
from app.errors import BadRequest
from app.models import Role
from app.services import channel_service as svc

channel_bp = Blueprint('channel', __name__, url_prefix='/workspaces/<uuid:workspace_id>/channels')

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,78}[a-z0-9]$|^[a-z0-9]$")

def _json(ch):
    return {"id": str(ch.id), "name": ch.name, "created_at": ch.created_at.isoformat()}

@channel_bp.get('')
@require_role(Role.MEMBER)
def list_all(workspace_id):
    return jsonify([_json(c) for c in svc.list_channels(workspace_id)])


@channel_bp.post('')
@require_role(Role.ADMIN)
def create(workspace_id):
    data = request.get_json() or {}
    name = (data.get('name') or '').strip().lower()
    if not NAME_RE.match(name):
        raise BadRequest('name must be 1-80 chars: lowercase letters, digits, hyphens')
    return jsonify(_json(svc.create_channel(workspace_id, g.current_user, name))), 201


@channel_bp.get('/<uuid:channel_id>')
@require_role(Role.MEMBER)
def get_one(workspace_id, channel_id):
    return jsonify(_json(svc.get_channel(workspace_id, channel_id)))


@channel_bp.delete('/<uuid:channel_id>')
@require_role(Role.ADMIN)
def delete(workspace_id, channel_id):
    svc.delete_channel(svc.get_channel(workspace_id, channel_id))
    return '', 204



