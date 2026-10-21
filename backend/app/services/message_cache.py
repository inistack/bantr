import json
from app import metrics
from app.redis_client import get_redis
from flask import current_app
from app.services import message_cache


CACHE_SIZE = 50
CACHE_TTL_SECONDS = 3600


def _key(workspace_id, channel_id):
    return f"msgs:ws:{workspace_id}:ch:{channel_id}"


def fill(r, workspace_id, channel_id, messages) -> None:
    """Replace the cache with `messages` (oldest first, at most CACHE_SIZE)."""
    key = _key(workspace_id, channel_id)
    pipe = r.pipeline()
    pipe.delete(key)
    if messages:
        pipe.zadd(
            key,
            {json.dumps(m, sort_keys=True, separators=(",", ":")): m["seq"] for m in messages},
        )
        pipe.expire(key, CACHE_TTL_SECONDS)
    pipe.execute()


def read(r, workspace_id, channel_id, last_seq):
    if last_seq == 0:
        return []
    messages = [json.loads(m) for m in r.zrange(_key(workspace_id, channel_id), 0, -1)]
    expected = min(CACHE_SIZE, last_seq)
    wanted = list(range(last_seq - expected + 1, last_seq + 1))
    if [m["seq"] for m in messages] != wanted:
        return None
    return messages


def append(r, workspace_id, channel_id, message) -> bool:
    """Add one new message to an existing cache and trim to the newest CACHE_SIZE.

    Does nothing if the channel has no cache. Returns whether it appended."""
    key = _key(workspace_id, channel_id)
    if not r.exists(key):
        return False
    seq = message["seq"]
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, seq, seq)  
    pipe.zadd(key, {json.dumps(message, sort_keys=True, separators=(",", ":")): seq})
    pipe.zremrangebyrank(key, 0, -(CACHE_SIZE + 1))  
    pipe.expire(key, CACHE_TTL_SECONDS)
    pipe.execute()
    return True

