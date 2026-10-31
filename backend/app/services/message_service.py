from sqlalchemy import update
from sqlalchemy.orm import selectinload

from app.errors import BadRequest, NotFound
from app.extensions import db
from app.models import Channel, Message
from app.services.channel_service import get_channel
from app.services.scoping import scoped_select
import redis
from flask import current_app

from app import metrics
from app.redis_client import get_redis
from app.serializers import message_to_dict
from app.services import message_cache
import structlog


log = structlog.get_logger(__name__)



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


def _from_database(workspace_id, channel, limit):
    rows = list_messages(workspace_id, channel.id, limit=limit)
    return [message_to_dict(m) for m in rows]


def _read_cache(r, workspace_id, channel):
    """The validated cached window, or None (a miss, damaged contents, or Redis trouble)."""
    try:
        return message_cache.read(r, workspace_id, channel.id, channel.last_seq)
    except (redis.RedisError, ValueError, KeyError, TypeError):
        log.exception("message_cache.read_failed")
        metrics.cache_result("error")
        return None


def _fill_cache(r, workspace_id, channel, messages):
    try:
        message_cache.fill(r, workspace_id, channel.id, messages[-message_cache.CACHE_SIZE:])
    except redis.RedisError:
        log.exception("message_cache.fill_failed")
        metrics.cache_result("error")


def recent_messages(workspace_id, channel_id, limit=50):
    """The newest `limit` messages as JSON-ready dicts, oldest first.

    Served from the Redis cache when it is complete and current, else from Postgres."""
    limit = max(1, min(limit, MAX_LIMIT))
    channel = get_channel(workspace_id, channel_id) 
    if channel.last_seq == 0:
        return []

    r = get_redis() if current_app.config["MESSAGE_CACHE_ENABLED"] else None
    if r is None or limit > message_cache.CACHE_SIZE:
        # No cache configured, or the request is bigger than the window we keep.
        return _from_database(workspace_id, channel, limit)

    window = _read_cache(r, workspace_id, channel)
    if window is not None:
        metrics.cache_result("hit")
        log.info("message_cache.hit", workspace_id=str(workspace_id), channel_id=str(channel.id))
        return window[-limit:]

    metrics.cache_result("miss")
    log.info("message_cache.miss", workspace_id=str(workspace_id), channel_id=str(channel.id))
    messages = _from_database(workspace_id, channel, message_cache.CACHE_SIZE)
    _fill_cache(r, workspace_id, channel, messages)
    return messages[-limit:]


def cache_new_message(workspace_id, channel_id, payload):
    """Write-through: add a just-committed message (already serialized) to the cache."""
    r = get_redis() if current_app.config["MESSAGE_CACHE_ENABLED"] else None
    if r is None:
        return
    try:
        message_cache.append(r, workspace_id, channel_id, payload)
    except redis.RedisError:
        # Harmless: the next read sees a stale window and rebuilds it.
        log.exception("message_cache.write_through_failed")
        metrics.cache_result("error")