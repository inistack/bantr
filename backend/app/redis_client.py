import redis
from flask import current_app

def init_redis(app):
    url = app.config.get('REDIS_URL')
    app.extensions['redis'] = redis.Redis.from_url(url, decode_responses=True) if url else None


def get_redis():
    return current_app.extensions.get('redis')
