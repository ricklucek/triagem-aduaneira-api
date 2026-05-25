from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from .base import TimestampMixin, uuid_pk


class PasswordMixin:
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Organization(TimestampMixin, db.Model):
    __tablename__ = "organizations"

    id = uuid_pk()
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    tax_id = db.Column(db.String(14), nullable=True, unique=True, index=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(64), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    users = db.relationship("User", back_populates="organization", lazy=True)
    clients = db.relationship("Client", back_populates="organization", lazy=True)
    scopes = db.relationship("Scope", back_populates="organization", lazy=True)
    prepostos = db.relationship("Preposto", back_populates="organization", lazy=True)
    settings = db.relationship(
        "OrganizationSetting",
        back_populates="organization",
        lazy=True,
        cascade="all, delete-orphan",
    )


class User(PasswordMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=True, index=True)

    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    role = db.Column(db.String(32), nullable=False, default="user")
    department = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization", back_populates="users")
    admin_profile = db.relationship("AdminProfile", uselist=False, back_populates="user", cascade="all, delete-orphan")
    assigned_scopes = db.relationship("ScopeAssignment", foreign_keys="ScopeAssignment.user_id", back_populates="user", lazy=True)


class AdminProfile(TimestampMixin, db.Model):
    __tablename__ = "admin_profiles"

    id = uuid_pk()
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, unique=True, index=True)

    is_super_admin = db.Column(db.Boolean, nullable=False, default=False)
    can_manage_users = db.Column(db.Boolean, nullable=False, default=True)
    can_manage_settings = db.Column(db.Boolean, nullable=False, default=True)
    can_manage_billing = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="admin_profile")


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = uuid_pk()
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, index=True)
    token = db.Column(db.String(1024), nullable=False, unique=True, index=True)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
