from marshmallow import Schema, fields

from app.models.enums import ScopeStatus
from app.schemas.common import EnumField, UUIDStringField
from app.schemas.clients import ClientPayloadSchema, ClientContactPayloadSchema
from .operations import ScopeOperationsPayloadSchema
from .taxes import ScopeTaxesPayloadSchema
from .services import ScopeServicesPayloadSchema
from .financial import ScopeFinancialPayloadSchema, ScopeGeneralPayloadSchema


class ScopeAssignmentsPayloadSchema(Schema):
    commercialResponsibleId = UUIDStringField(allow_none=True, load_default=None)
    importDaAnalystIds = fields.List(UUIDStringField(), load_default=[])
    importAeAnalystIds = fields.List(UUIDStringField(), load_default=[])
    exportDaAnalystIds = fields.List(UUIDStringField(), load_default=[])
    exportAeAnalystIds = fields.List(UUIDStringField(), load_default=[])


class ScopeDraftPayloadSchema(Schema):

    company = fields.Nested(ClientPayloadSchema, allow_none=True, load_default={})
    contacts = fields.List(fields.Nested(ClientContactPayloadSchema), load_default=[])
    assignments = fields.Nested(ScopeAssignmentsPayloadSchema, load_default={})
    operations = fields.Nested(ScopeOperationsPayloadSchema, load_default={})
    taxes = fields.Nested(ScopeTaxesPayloadSchema, load_default={})
    services = fields.Nested(ScopeServicesPayloadSchema, load_default={})
    financial = fields.Nested(ScopeFinancialPayloadSchema, allow_none=True, load_default=None)
    general = fields.Nested(ScopeGeneralPayloadSchema, allow_none=True, load_default=None)


class ScopeCreatePayloadSchema(ScopeDraftPayloadSchema):
    pass


class ScopeUpdatePayloadSchema(ScopeDraftPayloadSchema):
    status = EnumField(ScopeStatus, required=False)


class ScopeDraftResponseSchema(Schema):
    id = UUIDStringField()
    status = EnumField(ScopeStatus)
    version = fields.Integer()
    draft = fields.Nested(ScopeDraftPayloadSchema)
