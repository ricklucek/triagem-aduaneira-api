from marshmallow import Schema, ValidationError, fields, validates_schema

from app.models.enums import AssignmentRole, OperationType, ScopeStatus
from app.schemas.common import UUIDStringField, EnumField
from app.schemas.clients import ClientPayloadSchema, ClientContactPayloadSchema
from .operations import ScopeOperationsPayloadSchema
from .taxes import ScopeTaxesPayloadSchema
from .services import ScopeServicesPayloadSchema
from .financial import ScopeFinancialPayloadSchema, ScopeGeneralPayloadSchema


class ScopeAssignmentsPayloadSchema(Schema):
    commercialResponsibleUserId = UUIDStringField(
        attribute="commercial_responsible_user_id",
        allow_none=True,
        load_default=None,
    )
    importDaAnalystIds = fields.List(UUIDStringField(), load_default=[])
    importAeAnalystIds = fields.List(UUIDStringField(), load_default=[])
    exportDaAnalystIds = fields.List(UUIDStringField(), load_default=[])
    exportAeAnalystIds = fields.List(UUIDStringField(), load_default=[])


class ScopeCreatePayloadSchema(Schema):
    company = fields.Nested(ClientPayloadSchema, required=True)
    contacts = fields.List(fields.Nested(ClientContactPayloadSchema), load_default=[])
    assignments = fields.Nested(ScopeAssignmentsPayloadSchema, load_default={})
    operations = fields.Nested(ScopeOperationsPayloadSchema, required=True)
    taxes = fields.Nested(ScopeTaxesPayloadSchema, load_default={})
    services = fields.Nested(ScopeServicesPayloadSchema, load_default={})
    financial = fields.Nested(ScopeFinancialPayloadSchema, allow_none=True, load_default=None)
    general = fields.Nested(ScopeGeneralPayloadSchema, allow_none=True, load_default=None)


class ScopeUpdatePayloadSchema(Schema):
    status = EnumField(ScopeStatus, required=False)
    company = fields.Nested(ClientPayloadSchema, required=False)
    contacts = fields.List(fields.Nested(ClientContactPayloadSchema), required=False)
    assignments = fields.Nested(ScopeAssignmentsPayloadSchema, required=False)
    operations = fields.Nested(ScopeOperationsPayloadSchema, required=False)
    taxes = fields.Nested(ScopeTaxesPayloadSchema, required=False)
    services = fields.Nested(ScopeServicesPayloadSchema, required=False)
    financial = fields.Nested(ScopeFinancialPayloadSchema, allow_none=True, required=False)
    general = fields.Nested(ScopeGeneralPayloadSchema, allow_none=True, required=False)
