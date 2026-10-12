from sqlalchemy.exc import IntegrityError

from app.errors import Conflict
from app.extensions import db
from app.models import Channel
from app.services.scoping import get_in_workspace, scoped_select

def create_channel(workspace_id, user, name):
    channel = Channel(workspace_id=workspace_id, name=name, created_by=user.id)
    db.session.add(channel)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict(f'A channel with that name already exists')
    return channel


def list_channels(workspace_id):
    query = scoped_select(Channel, workspace_id).order_by(Channel.name)
    return db.session.scalars(query).all()


def get_channel(workspace_id, channel_id):
    return get_in_workspace(Channel, workspace_id, channel_id)


def delete_channel(channel):
    db.session.delete(channel)
    db.session.commit()

