import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, String, Boolean, BigInteger, ForeignKeyConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from app.extensions import db
from app.models.base import utcnow


class Channel(db.Model):
    __tablename__ = 'channels'
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_channel_workspace_name"),
        UniqueConstraint("id", "workspace_id", name="uq_channel_id_workspace"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('workspaces.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    last_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Message(db.Model):
    __tablename__ = 'messages'
    __table_args__ = (
        UniqueConstraint('channel_id', 'seq', name='uq_message_channel_seq'),
        ForeignKeyConstraint(
            ['channel_id', 'workspace_id'],
            ['channels.id', 'channels.workspace_id'],
            ondelete='CASCADE',
            name='fk_message_channel_workspace'
        )
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('workspaces.id', ondelete='CASCADE'), index=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    body: Mapped[str] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped['User'] = relationship()
    
