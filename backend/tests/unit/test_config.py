from app.config import missing_production_settings

GOOD = {
    "SECRET_KEY": "s" * 32,
    "JWT_SECRET_KEY": "j" * 32,
    "TOKEN_ENCRYPTION_KEY": "key",
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://u:p@db/x",
    "REDIS_URL": "redis://redis:6379/0",
}


def test_a_complete_configuration_has_no_problems():
    assert missing_production_settings(GOOD) == []


def test_each_missing_setting_is_reported():
    for key in GOOD:
        without = {k: v for k, v in GOOD.items() if k != key}
        assert any(key in problem for problem in missing_production_settings(without)), key


def test_the_development_secret_key_is_rejected():
    problems = missing_production_settings({**GOOD, "SECRET_KEY": "dev-only-change-me"})
    assert any("development default" in problem for problem in problems)


def test_a_short_jwt_key_is_rejected():
    problems = missing_production_settings({**GOOD, "JWT_SECRET_KEY": "short"})
    assert any("shorter than 32" in problem for problem in problems)
