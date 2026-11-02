from datetime import UTC, datetime, timedelta

import jwt
from flask import current_app

ALGORITHM = "HS256"

def issue_token(user_id):
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"]),
    }

    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm=ALGORITHM)


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )