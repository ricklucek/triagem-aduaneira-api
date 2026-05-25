from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import PricingType, ServiceOperationType, ServiceType, enum_column


class ServiceCatalog(TimestampMixin, db.Model):
    __tablename__ = "service_catalog"

    id = uuid_pk()
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey("organizations.id"), nullable=False, index=True)
    code = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    service_type = db.Column(enum_column(ServiceType, "service_type"), nullable=False, index=True)
    operation_type = db.Column(enum_column(ServiceOperationType, "service_operation_type"), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    organization = db.relationship("Organization")
    scope_services = db.relationship("ScopeService", back_populates="service_catalog", lazy=True)

    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_service_catalog_org_code"),)


class ScopeService(TimestampMixin, db.Model):
    __tablename__ = "scope_services"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, index=True)
    service_catalog_id = db.Column(UUID(as_uuid=True), db.ForeignKey("service_catalog.id"), nullable=False, index=True)
    operation_type = db.Column(enum_column(ServiceOperationType, "scope_service_operation_type"), nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    pricing_type = db.Column(enum_column(PricingType, "scope_service_pricing_type"), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="BRL")
    responsible_user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True, index=True)
    last_updated_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    scope = db.relationship("Scope", back_populates="services")
    service_catalog = db.relationship("ServiceCatalog", back_populates="scope_services")
    responsible_user = db.relationship("User")

    freight_detail = db.relationship("ScopeServiceFreightDetail", back_populates="scope_service", uselist=False, cascade="all, delete-orphan")
    insurance_detail = db.relationship("ScopeServiceInsuranceDetail", back_populates="scope_service", uselist=False, cascade="all, delete-orphan")
    customs_broker_detail = db.relationship("ScopeServiceCustomsBrokerDetail", back_populates="scope_service", uselist=False, cascade="all, delete-orphan")
    certificate_detail = db.relationship("ScopeServiceCertificateDetail", back_populates="scope_service", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("scope_id", "service_catalog_id", "operation_type", name="uq_scope_service_unique"),)


class ScopeServiceFreightDetail(TimestampMixin, db.Model):
    __tablename__ = "scope_service_freight_details"

    id = uuid_pk()
    scope_service_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_services.id"), nullable=False, unique=True, index=True)
    mode = db.Column(db.String(64), nullable=True)
    negotiated_ptax = db.Column(db.Numeric(12, 4), nullable=True)
    general_notes = db.Column(db.Text, nullable=True)

    scope_service = db.relationship("ScopeService", back_populates="freight_detail")


class ScopeServiceInsuranceDetail(TimestampMixin, db.Model):
    __tablename__ = "scope_service_insurance_details"

    id = uuid_pk()
    scope_service_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_services.id"), nullable=False, unique=True, index=True)
    minimum_amount = db.Column(db.Numeric(12, 2), nullable=True)
    cfr_percentage = db.Column(db.Numeric(8, 4), nullable=True)
    policy_inclusion_date = db.Column(db.Date, nullable=True)
    additional_description = db.Column(db.Text, nullable=True)

    scope_service = db.relationship("ScopeService", back_populates="insurance_detail")


class ScopeServiceCustomsBrokerDetail(TimestampMixin, db.Model):
    __tablename__ = "scope_service_customs_broker_details"

    id = uuid_pk()
    scope_service_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_services.id"), nullable=False, unique=True, index=True)
    salary_multiplier = db.Column(db.Numeric(8, 4), nullable=True)
    pricing_reference = db.Column(db.String(64), nullable=True)

    scope_service = db.relationship("ScopeService", back_populates="customs_broker_detail")


class ScopeServiceCertificateDetail(TimestampMixin, db.Model):
    __tablename__ = "scope_service_certificate_details"

    id = uuid_pk()
    scope_service_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_services.id"), nullable=False, unique=True, index=True)
    certificate_name = db.Column(db.String(255), nullable=True)
    issuing_authority = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    scope_service = db.relationship("ScopeService", back_populates="certificate_detail")
