from datetime import datetime, timezone
from sqlalchemy import select
from app.extensions import db
from app.models.user import User, OAuthAccount
from app.auth.crypto import encrypt

def login_with_oauth(*, provider, provider_user_id, email, name, avatar_url, token):
    account = db.session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id
        )
    )

    if account is None:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=name, avatar_url=avatar_url)
            db.session.add(user)
        account = OAuthAccount(
            user=user,
            provider=provider,
            provider_user_id=provider_user_id
        )
        db.session.add(account)

    expires_at = token.get('expires_at')
    account.access_token = encrypt(token.get("access_token"))
    account.refresh_token = encrypt(token.get("refresh_token"))
    account.expires_at = (
            datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None
    )
    db.session.commit()
    return account.user
