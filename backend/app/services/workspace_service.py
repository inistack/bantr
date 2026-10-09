from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.errors import Conflict, Forbidden, NotFound
from app.extensions import db
from app.models import ROLE_RANK, Membership, Role, User, Workspace

def create_workspace(user, name, slug):
    workspace = Workspace(name=name, slug=slug, created_by=user.id)
    workspace.memberships.append(Membership(user_id=user.id, role=Role.OWNER))
    db.session.add(workspace)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict('That workspace URL name is already taken')
    return workspace


def list_workspaces(user):
    rows = db.session.execute(
        select(User, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.name)
    ).all()
    return [(ws, role) for ws, role in rows]


def list_members(workspace_id):
    rows = db.session.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.name)
    ).all()
    return [(user, role) for user, role in rows]


def add_member(workspace_id, actor_membership, email, role):
    if ROLE_RANK[role] >= ROLE_RANK[actor_membership.role]:
        raise Forbidden('You can only grant roles below your own')
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        raise NotFound('No user with that email')
    db.session.add(Membership(user_id=user.id, workspace_id=workspace_id, role=role))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict('User is already a member')
    return user

def delete_workspace(workspace):
    db.session.delete(workspace)
    db.session.commit()