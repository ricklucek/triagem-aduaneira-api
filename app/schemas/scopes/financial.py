from marshmallow import Schema, fields

from app.models.enums import PaymentPreference
from app.schemas.common import EnumField, UUIDStringField


class RefundBankAccountSchema(Schema):
    id = UUIDStringField(dump_only=True)
    bankName = fields.String(attribute="bank_name", allow_none=True)
    branch = fields.String(allow_none=True)
    account = fields.String(allow_none=True)


class ScopeFinancialSchema(Schema):
    id = UUIDStringField(dump_only=True)
    paymentPreference = EnumField(PaymentPreference, attribute="payment_preference", allow_none=True)
    refundPixKey = fields.String(attribute="refund_pix_key", allow_none=True)
    notes = fields.String(allow_none=True)
    refundBankAccounts = fields.Nested(
        RefundBankAccountSchema,
        attribute="refund_bank_accounts",
        many=True,
    )


class ScopeGeneralSchema(Schema):
    id = UUIDStringField(dump_only=True)
    description = fields.String(allow_none=True)


class RefundBankAccountPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    bankName = fields.String(attribute="bank_name", allow_none=True, load_default=None)
    branch = fields.String(allow_none=True, load_default=None)
    account = fields.String(allow_none=True, load_default=None)


class ScopeFinancialPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    paymentPreference = EnumField(PaymentPreference, attribute="payment_preference", allow_none=True, load_default=None)
    refundPixKey = fields.String(attribute="refund_pix_key", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)
    refundBankAccounts = fields.List(fields.Nested(RefundBankAccountPayloadSchema), load_default=[])


class ScopeGeneralPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    description = fields.String(allow_none=True, load_default=None)
