from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import AssignmentRole, OperationType, ScopeStatus, enum_column


class Scope(TimestampMixin, db.Model):
    __tablename__ = "scopes"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=False, index=True)
    client_id = db.Column(UUID(as_uuid=True), db.ForeignKey("clients.id"), nullable=False, index=True)

    status = db.Column(enum_column(ScopeStatus, "scope_status"), nullable=False, default=ScopeStatus.DRAFT, index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    commercial_responsible_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, index=True)
    last_published_at = db.Column(db.DateTime, nullable=True)

    # Legacy only during migration. Do not use as source of truth.
    legacy_draft = db.Column("draft", db.JSON, nullable=True)
    published_snapshot = db.Column(db.JSON, nullable=True)
    relational_migrated_at = db.Column(db.DateTime, nullable=True)
    legacy_draft_hash = db.Column(db.String(64), nullable=True)

    organization = db.relationship("Organization", back_populates="scopes")
    client = db.relationship("Client", back_populates="scopes")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    commercial_responsible_user = db.relationship("User", foreign_keys=[commercial_responsible_user_id])

    assignments = db.relationship("ScopeAssignment", back_populates="scope", lazy=True, cascade="all, delete-orphan")
    operation_profile = db.relationship("ScopeOperationProfile", back_populates="scope", uselist=False, cascade="all, delete-orphan")
    operation_details = db.relationship("ScopeOperationDetail", back_populates="scope", lazy=True, cascade="all, delete-orphan")
    services = db.relationship("ScopeService", back_populates="scope", lazy=True, cascade="all, delete-orphan")
    prepostos = db.relationship("ScopePreposto", back_populates="scope", lazy=True, cascade="all, delete-orphan")
    financial_profile = db.relationship("ScopeFinancialProfile", back_populates="scope", uselist=False, cascade="all, delete-orphan")
    general_profile = db.relationship("ScopeGeneralProfile", back_populates="scope", uselist=False, cascade="all, delete-orphan")
    versions = db.relationship("ScopeVersion", back_populates="scope", lazy=True, cascade="all, delete-orphan", order_by="desc(ScopeVersion.version_number)")

    @property
    def active_assignments(self):
        return [item for item in self.assignments if item.active]

    def assignments_by_role(self, role: AssignmentRole | str):
        role_value = role.value if isinstance(role, AssignmentRole) else role
        return [item for item in self.active_assignments if item.role == role_value]

    @property
    def import_operation(self):
        return next((item for item in self.operation_details if item.operation_type == OperationType.IMPORT.value), None)

    @property
    def export_operation(self):
        return next((item for item in self.operation_details if item.operation_type == OperationType.EXPORT.value), None)


class ScopeVersion(db.Model):
    __tablename__ = "scope_versions"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    created_by_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scope = db.relationship("Scope", back_populates="versions")
    created_by = db.relationship("User")

    __table_args__ = (UniqueConstraint("scope_id", "version_number", name="uq_scope_versions_scope_version"),)


class ScopeAssignment(TimestampMixin, db.Model):
    __tablename__ = "scope_assignments"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, index=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(enum_column(AssignmentRole, "scope_assignment_role"), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=True)

    scope = db.relationship("Scope", back_populates="assignments")
    user = db.relationship("User", back_populates="assigned_scopes")

    __table_args__ = (
        db.Index("ix_scope_assignments_scope_role_active", "scope_id", "role", "active"),
        db.Index("ix_scope_assignments_user_role_active", "user_id", "role", "active"),
    )
