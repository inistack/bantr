import re
from flask import g, Blueprint, jsonify, request
from app.auth.decorators import login_required, require_role
from app.errors import BadRequest
from app.models import Role
from app.services import workspace_service as svc

workspace_bp = Blueprint("workspaces", __name__, url_prefix="/workspaces")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")

def _ws_json(ws, role):
    return {"id": str(ws.id), "name": ws.name, "slug": ws.slug, "role": role.value}

@workspace_bp.post("")
@login_required
def create():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    slug = (data.get("slug") or "").strip().lower()

    if not name or len(name) > 100:
        raise BadRequest("name is required (max 100 characters)")
    if not SLUG_RE.match(slug):
        raise BadRequest("slug must be 3-60 chars: lowercase letters, digits, hyphens")
    ws = svc.create_workspace(g.current_user, name, slug)
    return jsonify(_ws_json(ws, Role.OWNER)), 201


@workspace_bp.get("")
@login_required
def list_mine():
    return jsonify([_ws_json(ws, role) for ws, role in svc.list_workspaces(g.current_user)])


@workspace_bp.get("/<uuid:workspace_id>")
@require_role(Role.MEMBER)
def get_one(workspace_id):
    return jsonify(_ws_json(g.membership.workspace, g.membership.role))


@workspace_bp.get("/<uuid:workspace_id>/members")
@require_role(Role.MEMBER)
def members(workspace_id):
    return jsonify(
        [
            {"id": str(u.id), "name": u.name, "email": u.email, "role": role.value}
            for u, role in svc.list_members(workspace_id)
        ]
    )


@workspace_bp.post("/<uuid:workspace_id>/members")
@require_role(Role.ADMIN)
def add_member(workspace_id):
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    try:
        role = Role(data.get("role", "member"))
    except ValueError:
        raise BadRequest("role must be one of: owner, admin, member")
    if not email:
        raise BadRequest("email is required")
    user = svc.add_member(workspace_id, g.membership, email, role)
    return jsonify(id=str(user.id), email=user.email, role=role.value), 201


@workspace_bp.delete("/<uuid:workspace_id>")
@require_role(Role.OWNER)
def delete(workspace_id):
    svc.delete_workspace(g.membership.workspace)
    return "", 204