from marshmallow import Schema, fields

from app.models.enums import (
    AccountOwnerType,
    AssignmentRole,
    DestinationPurpose,
    LocationType,
    OperationType,
    PaymentPreference,
    PricingType,
    ScopeStatus,
    ServiceOperationType,
    ServiceType,
    TaxRegime,
)
from app.schemas.common import EnumField, UUIDStringField


class BankAccountSchema(Schema):
    bankName = fields.String(attribute="bank_name", allow_none=True)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True)
    bankAccount = fields.String(attribute="bank_account", allow_none=True)


class SimpleBankAccountPayloadSchema(Schema):
    bankName = fields.String(attribute="bank_name", allow_none=True, load_default=None)
    branch = fields.String(allow_none=True, load_default=None)
    account = fields.String(allow_none=True, load_default=None)


class UserIdListPayloadSchema(Schema):
    ids = fields.List(UUIDStringField(), load_default=[])
