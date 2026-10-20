def message_to_dict(m) -> dict:
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