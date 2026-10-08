import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db
from app.models.base import utcnow


class User(db.Model):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    oauth_accounts: Mapped[list['OAuthAccount']] = relationship(back_populates='user', cascade='all, delete-orphan')
    memberships: Mapped[list['Membership']] = relationship(back_populates="user", cascade="all, delete-orphan")


class OAuthAccount(db.Model):
    __tablename__ = 'oauth_accounts'
    __table_args__ = (UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user'),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped['User'] = relationship(back_populates='oauth_accounts')

