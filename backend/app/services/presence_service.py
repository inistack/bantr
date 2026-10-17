def _key(workspace_id):
    return f'presence:ws:{workspace_id}'


def _member(user_id, sid):
    return f'{user_id}|{sid}'


def _user_of(member):
    return member.split('|', 1)[0]


def _live_members(r, workspace_id, now, ttl):
    return r.zrangebyscore(_key(workspace_id), now - ttl, "+inf")


def user_is_live(r, workspace_id, user_id, now, ttl):
    prefix = f'{user_id}|'
    return any(m.startswith(prefix) for m in _live_members(r, workspace_id, now, ttl))


def online_user_ids(r, workspace_id, now, ttl):
    return sorted({_user_of(m) for m in _live_members(r, workspace_id, now, ttl)})


def add_connection(r, workspace_ids, user_id, sid, now, ttl):
    """Register a connection. Returns the workspaces where the user just came online."""
    came_online = []
    for ws in workspace_ids:
        was_online = user_is_live(r, ws, user_id, now, ttl)
        r.zadd(_key(ws), {_member(user_id, sid): now})
        if not was_online:
            came_online.append(ws)
    return came_online


def remove_connection(r, workspace_ids, user_id, sid, now, ttl):
    """Unregister a connection. Returns the workspaces where the user just went offline."""
    went_offline = []
    for ws in workspace_ids:
        removed = r.zrem(_key(ws), _member(user_id, sid))
        if removed and not user_is_live(r, ws, user_id, now, ttl):
            went_offline.append(ws)
    return went_offline


def heartbeat(r, entries, now):
    """Refresh connections. `entries` is [(workspace_ids, user_id, sid), ...].

    Returns (workspace_id, user_id) pairs whose entry had been *missing* and was
    re-created: it was reaped after a stall, or Redis lost its data. The caller
    announces those users as online again."""
    pipe = r.pipeline()
    order = []
    for workspace_ids, user_id, sid in entries:
        for ws in workspace_ids:
            pipe.zadd(_key(ws), {_member(user_id, sid): now})
            order.append((ws, user_id))
    results = pipe.execute()
    return [pair for pair, added in zip(order, results) if added]


def reap_stale(r, workspace_id, now, ttl):
    """Remove expired entries. Returns users who went offline because of it.

    Only the caller whose ZREM actually removed an entry reports it, so several
    processes reaping the same workspace never announce the same user twice."""
    stale = r.zrangebyscore(_key(workspace_id), "-inf", f"({now - ttl}")
    went_offline = set()
    for member in stale:
        if r.zrem(_key(workspace_id), member):
            user_id = _user_of(member)
            if not user_is_live(r, workspace_id, user_id, now, ttl):
                went_offline.add(user_id)
    return sorted(went_offline)

