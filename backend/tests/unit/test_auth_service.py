from sqlalchemy import func, select

from app.auth.crypto import decrypt
from app.extensions import db
from app.models import OAuthAccount, User
from app.services.auth_service import login_with_oauth

TOKEN = {"access_token": "tok-123", "refresh_token": "ref-456", "expires_at": 1900000000}


def login(provider="github", provider_user_id="1", email="a@test.dev"):
    return login_with_oauth(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name="Ada",
        avatar_url=None,
        token=TOKEN,
    )


def count(model):
    return db.session.scalar(select(func.count()).select_from(model))


def test_new_identity_creates_user_and_encrypted_account(app):
    with app.app_context():
        login()
        account = db.session.scalar(select(OAuthAccount))
        assert count(User) == 1
        assert account.access_token != "tok-123"      
        assert decrypt(account.access_token) == "tok-123"
        assert decrypt(account.refresh_token) == "ref-456"


def test_returning_identity_does_not_duplicate(app):
    with app.app_context():
        first = login()
        second = login()
        assert first.id == second.id
        assert count(User) == 1
        assert count(OAuthAccount) == 1


def test_second_provider_with_same_verified_email_links_to_same_user(app):
    with app.app_context():
        first = login(provider="github", provider_user_id="1")
        second = login(provider="google", provider_user_id="abc")
        assert first.id == second.id
        assert count(User) == 1
        assert count(OAuthAccount) == 2