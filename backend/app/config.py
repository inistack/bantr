import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "development-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
    TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    JWT_EXPIRES_MINUTES = 60
    COOKIE_SECURE = False
    SOCKETIO_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    REDIS_URL = os.environ.get("REDIS_URL")
    PRESENCE_TTL_SECONDS = 30
    PRESENCE_HEARTBEAT_SECONDS = 10
    MESSAGE_CACHE_ENABLED = os.environ.get("MESSAGE_CACHE_ENABLED", "1") == "1"
    MESSAGE_RATE_LIMIT = os.environ.get("MESSAGE_RATE_LIMIT", "5 per second;60 per minute")
    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL") or "memory://"
    RATELIMIT_STRATEGY = "moving-window"
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = True
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True
    LOG_FORMAT = os.environ.get("LOG_FORMAT", "console")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    METRICS_TOKEN = os.environ.get("METRICS_TOKEN")
    SOCKETIO_CHANNEL = os.environ.get("SOCKETIO_CHANNEL", "bantr")


class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL")
    SECRET_KEY = "test-secret-key-for-sessions-only"
    JWT_SECRET_KEY = "test-jwt-secret-key-at-least-32-bytes-long"
    TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode()
    REDIS_URL = None
    MESSAGE_CACHE_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"
    MESSAGE_RATE_LIMIT = "100000 per second"
    LOG_LEVEL = "WARNING"
    METRICS_TOKEN = None

class E2EConfig(TestingConfig):
    """Used by the real server processes that tests/e2e starts."""

    TESTING = False  # the presence heartbeat is skipped when the app is in testing mode
    REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
    RATELIMIT_STORAGE_URI = REDIS_URL
    MESSAGE_RATE_LIMIT = os.environ.get("E2E_MESSAGE_RATE_LIMIT", "100000 per second")
    PRESENCE_TTL_SECONDS = 3
    PRESENCE_HEARTBEAT_SECONDS = 1
    SOCKETIO_CORS_ORIGINS = "*"  # random ports; test config only
    LOG_LEVEL = "WARNING"

class ProductionConfig(Config):
    DEBUG = False
    COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "e2e": E2EConfig,
}

