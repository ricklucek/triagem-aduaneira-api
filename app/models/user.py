from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.utils import PasswordMixin, TimestampMixin, uuid_pk

from ..extensions import Base

class User(PasswordMixin, TimestampMixin, Base):
    __tablename__ = "users"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)

    role = Column(String(32), nullable=False, default="user")
    setor = Column(String(255), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)

    organization = relationship("Organization", back_populates="users")
    admin_profile = relationship(
        "AdminProfile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )

    assigned_scopes = relationship(
        "ScopeAssignment",
        foreign_keys="ScopeAssignment.user_id",
        back_populates="user",
        lazy=True,
    )

    tag_assignments = relationship(
        "UserTagAssignment",
        foreign_keys="UserTagAssignment.user_id",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class AdminProfile(TimestampMixin, Base):
    __tablename__ = "admin_profiles"

    id = uuid_pk()
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    is_super_admin = Column(Boolean, nullable=False, default=False)
    can_manage_users = Column(Boolean, nullable=False, default=True)
    can_manage_settings = Column(Boolean, nullable=False, default=True)
    can_manage_billing = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="admin_profile")


class UserTag(TimestampMixin, Base):
    __tablename__ = "user_tags"

    id = uuid_pk()
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    code = Column(String(64), nullable=False)
    name = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(24), nullable=False, default="slate")
    is_master = Column(Boolean, nullable=False, default=False)
    is_system = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_by = relationship("User", foreign_keys=[created_by_id])
    assignments = relationship(
        "UserTagAssignment",
        back_populates="tag",
        lazy=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_user_tags_org_code"),
    )


class UserTagAssignment(Base):
    __tablename__ = "user_tag_assignments"

    id = uuid_pk()
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    tag_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_tags.id"),
        nullable=False,
        index=True,
    )
    assigned_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="tag_assignments",
    )
    tag = relationship("UserTag", back_populates="assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_user_tag_assignments_user_tag"),
    )
