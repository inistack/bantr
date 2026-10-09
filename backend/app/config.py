import os
from dotenv import load_dotenv

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


class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL")


class ProductionConfig(Config):
    DEBUG = False
    COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

