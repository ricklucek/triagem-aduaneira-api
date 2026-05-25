from marshmallow import Schema, fields, validate

from app.models.enums import ScopeStatus
from app.schemas.common import EnumField, UUIDStringField


class ScopeListQuerySchema(Schema):
    status = EnumField(ScopeStatus, required=False)
    q = fields.String(required=False)
    taxId = fields.String(required=False)
    clientId = UUIDStringField(required=False)
    assignedUserId = UUIDStringField(required=False)
    commercialResponsibleUserId = UUIDStringField(required=False)
    createdById = UUIDStringField(required=False)
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))
