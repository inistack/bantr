import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, String, Enum 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.extensions import db
from app.models.base import utcnow

class Role(str, enum.Enum):
    OWNER = 'owner'
    ADMIN = 'admin'
    MEMBER = 'member'


class Workspace(db.Model):
    __tablename__ = 'workspaces'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    memberships: Mapped[list['Membership']] = relationship(back_populates='workspace', cascade='all, delete-orphan')


class Membership(db.Model):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_membership_user_workspace"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('workspaces.id', ondelete='CASCADE'), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]), default=Role.MEMBER)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped['User'] = relationship(back_populates='memberships')
    workspace: Mapped['Workspace'] = relationship(back_populates='memberships')