from sqlalchemy import update
from sqlalchemy.orm import selectinload

from app.errors import BadRequest, NotFound
from app.extensions import db
from app.models import Channel, Message
from app.services.channel_service import get_channel
from app.services.scoping import scoped_select


MAX_BODY = 4000
MAX_LIMIT = 100

def send_message(workspace_id, channel_id, user, body):
    seq = db.session.scalar(
        update(Channel)
        .where(Channel.id == channel_id, Channel.workspace_id == workspace_id)
        .values(last_seq=Channel.last_seq + 1)
        .returning(Channel.last_seq)
    )
    if seq is None:
        db.session.rollback()
        raise NotFound('Channel not found')
    
    message = Message(
        workspace_id=workspace_id,
        channel_id=channel_id,
        user_id = user.id,
        body=body,
        seq=seq
    )
    db.session.add(message)
    db.session.commit()
    return message


def list_messages(workspace_id, channel_id, *, after=None, before=None, limit=50):
    if after is not None and before is not None:
        raise BadRequest('Use either after or before, not both')
    limit = max(1, min(limit, MAX_LIMIT))

    get_channel(workspace_id, channel_id)

    query = (
        scoped_select(Message, workspace_id)
        .where(Message.channel_id == channel_id)
        .options(selectinload(Message.user))
    )

    if after is not None:
        return db.session.scalars(
            query.where(Message.seq > after).order_by(Message.seq.asc()).limit(limit)
        ).all()
    
    if before is not None:
        query = query.where(Message.seq < before)
    rows = db.session.scalars(
            query.order_by(Message.seq.desc()).limit(limit)
        ).all()
    return list(reversed(rows))