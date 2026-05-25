from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from .base import TimestampMixin, uuid_pk
from .enums import PaymentPreference, enum_column


class ScopeFinancialProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_financial_profiles"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, unique=True, index=True)
    payment_preference = db.Column(enum_column(PaymentPreference, "scope_payment_preference"), nullable=True)
    refund_pix_key = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    scope = db.relationship("Scope", back_populates="financial_profile")
    refund_bank_accounts = db.relationship("ScopeRefundBankAccount", back_populates="financial_profile", lazy=True, cascade="all, delete-orphan")


class ScopeRefundBankAccount(TimestampMixin, db.Model):
    __tablename__ = "scope_refund_bank_accounts"

    id = uuid_pk()
    financial_profile_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scope_financial_profiles.id"), nullable=False, index=True)
    bank_name = db.Column(db.String(255), nullable=True)
    branch = db.Column(db.String(64), nullable=True)
    account = db.Column(db.String(64), nullable=True)

    financial_profile = db.relationship("ScopeFinancialProfile", back_populates="refund_bank_accounts")


class ScopeGeneralProfile(TimestampMixin, db.Model):
    __tablename__ = "scope_general_profiles"

    id = uuid_pk()
    scope_id = db.Column(UUID(as_uuid=True), db.ForeignKey("scopes.id"), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)

    scope = db.relationship("Scope", back_populates="general_profile")
