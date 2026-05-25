from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import DestinationPurpose, LocationType, OperationType, enum_column


class ScopeOperationProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_profiles"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, unique=True, index=True)
    has_import = db.Column(db.Boolean, nullable=False, default=False)
    has_export = db.Column(db.Boolean, nullable=False, default=False)

    scope = db.relationship("Scope", back_populates="operation_profile")


class ScopeOperationDetail(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_details"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, index=True)
    operation_type = db.Column(enum_column(OperationType, "scope_operation_type"), nullable=False, index=True)

    products_description = db.Column(db.Text, nullable=True)
    ncm_notes = db.Column(db.Text, nullable=True)
    has_exporter_relationship = db.Column(db.Boolean, nullable=True)
    requires_dtc = db.Column(db.Boolean, nullable=True)
    requires_dta = db.Column(db.Boolean, nullable=True)
    requires_li_lpco = db.Column(db.Boolean, nullable=True)
    other_authority = db.Column(db.Text, nullable=True)

    scope = db.relationship("Scope", back_populates="operation_details")
    ncms = db.relationship("ScopeOperationNcm", back_populates="operation_detail", lazy=True, cascade="all, delete-orphan")
    locations = db.relationship("ScopeOperationLocation", back_populates="operation_detail", lazy=True, cascade="all, delete-orphan")
    authorities = db.relationship("ScopeOperationAuthority", back_populates="operation_detail", lazy=True, cascade="all, delete-orphan")
    destination_purposes = db.relationship("ScopeOperationDestinationPurpose", back_populates="operation_detail", lazy=True, cascade="all, delete-orphan")
    federal_tax_profile = db.relationship("ScopeFederalTaxProfile", back_populates="operation_detail", uselist=False, cascade="all, delete-orphan")
    afrmm_profile = db.relationship("ScopeAfrmmProfile", back_populates="operation_detail", uselist=False, cascade="all, delete-orphan")
    icms_profile = db.relationship("ScopeIcmsProfile", back_populates="operation_detail", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("scope_id", "operation_type", name="uq_scope_operation_detail_type"),)


class ScopeOperationNcm(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_ncms"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, index=True)
    code = db.Column(db.String(16), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="ncms")

    __table_args__ = (UniqueConstraint("operation_detail_id", "code", name="uq_scope_operation_ncm"),)


class ScopeOperationLocation(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_locations"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, index=True)
    location_type = db.Column(enum_column(LocationType, "scope_operation_location_type"), nullable=False, index=True)
    code = db.Column(db.String(32), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    raw_value = db.Column(db.String(255), nullable=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="locations")

    __table_args__ = (UniqueConstraint("operation_detail_id", "location_type", "raw_value", name="uq_scope_operation_location"),)


class ScopeOperationAuthority(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_authorities"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, index=True)
    code = db.Column(db.String(64), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="authorities")

    __table_args__ = (UniqueConstraint("operation_detail_id", "name", name="uq_scope_operation_authority_name"),)


class ScopeOperationDestinationPurpose(TimestampMixin, db.Model):
    __tablename__ = "scope_operation_destination_purposes"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, index=True)
    purpose = db.Column(enum_column(DestinationPurpose, "scope_destination_purpose"), nullable=False, index=True)
    consumption_subtype = db.Column(db.String(64), nullable=True, index=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="destination_purposes")

    __table_args__ = (
        UniqueConstraint("operation_detail_id", "purpose", "consumption_subtype", name="uq_scope_operation_destination_purpose"),
    )
