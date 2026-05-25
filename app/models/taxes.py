from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import AccountOwnerType, DestinationPurpose, TaxRegime, enum_column


class ScopeFederalTaxProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_federal_tax_profiles"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, unique=True, index=True)
    payment_account_type = db.Column(enum_column(AccountOwnerType, "federal_tax_payment_account_type"), nullable=False, default=AccountOwnerType.CASCO)
    bank_name = db.Column(db.String(255), nullable=True)
    bank_branch = db.Column(db.String(64), nullable=True)
    bank_account = db.Column(db.String(64), nullable=True)

    ii_regime = db.Column(enum_column(TaxRegime, "ii_tax_regime"), nullable=True)
    ii_benefit_detail = db.Column(db.Text, nullable=True)
    ipi_regime = db.Column(enum_column(TaxRegime, "ipi_tax_regime"), nullable=True)
    ipi_benefit_detail = db.Column(db.Text, nullable=True)
    pis_regime = db.Column(enum_column(TaxRegime, "pis_tax_regime"), nullable=True)
    pis_benefit_detail = db.Column(db.Text, nullable=True)
    cofins_regime = db.Column(enum_column(TaxRegime, "cofins_tax_regime"), nullable=True)
    cofins_benefit_detail = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="federal_tax_profile")


class ScopeAfrmmProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_afrmm_profiles"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, unique=True, index=True)
    payment_account_type = db.Column(enum_column(AccountOwnerType, "afrmm_payment_account_type"), nullable=False, default=AccountOwnerType.CASCO)
    bank_name = db.Column(db.String(255), nullable=True)
    bank_branch = db.Column(db.String(64), nullable=True)
    bank_account = db.Column(db.String(64), nullable=True)
    regime = db.Column(enum_column(TaxRegime, "afrmm_tax_regime"), nullable=True)
    benefit_detail = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="afrmm_profile")


class ScopeIcmsProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_icms_profiles"

    id = uuid_pk()
    operation_detail_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_operation_details.id"), nullable=False, unique=True, index=True)
    payment_account_type = db.Column(enum_column(AccountOwnerType, "icms_payment_account_type"), nullable=False, default=AccountOwnerType.CASCO)
    bank_name = db.Column(db.String(255), nullable=True)
    bank_branch = db.Column(db.String(64), nullable=True)
    bank_account = db.Column(db.String(64), nullable=True)
    regime = db.Column(enum_column(TaxRegime, "icms_tax_regime"), nullable=True)
    collected_rate = db.Column(db.Numeric(8, 4), nullable=True)
    effective_rate = db.Column(db.Numeric(8, 4), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    operation_detail = db.relationship("ScopeOperationDetail", back_populates="icms_profile")
    destination_rates = db.relationship("ScopeIcmsDestinationRate", back_populates="icms_profile", lazy=True, cascade="all, delete-orphan")


class ScopeIcmsDestinationRate(TimestampMixin, db.Model):
    __tablename__ = "scope_icms_destination_rates"

    id = uuid_pk()
    icms_profile_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_icms_profiles.id"), nullable=False, index=True)
    destination_purpose = db.Column(enum_column(DestinationPurpose, "icms_destination_purpose"), nullable=False, index=True)
    collected_rate = db.Column(db.Numeric(8, 4), nullable=True)
    effective_rate = db.Column(db.Numeric(8, 4), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    icms_profile = db.relationship("ScopeIcmsProfile", back_populates="destination_rates")

    __table_args__ = (UniqueConstraint("icms_profile_id", "destination_purpose", name="uq_scope_icms_destination_rate"),)
