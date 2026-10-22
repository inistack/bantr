import jwt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.auth.decorators import _extract_token
from app.auth.tokens import decode_token

def rate_limit_key():
    """Limit per user when the request carries a valid token, otherwise per IP."""
    token = _extract_token()
    if token:
        try:
            return f"user:{decode_token(token)['sub']}"
        except jwt.InvalidTokenError:
            pass
    return f"ip:{get_remote_address()}"

limiter = Limiter(key_func=rate_limit_key)

