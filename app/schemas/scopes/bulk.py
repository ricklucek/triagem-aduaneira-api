from marshmallow import Schema, fields, validate, validates_schema, ValidationError

from app.schemas.common import UUIDStringField


BULK_ASSIGNMENT_GROUPS = (
    "commercial_responsible",
    "import_da_analyst",
    "import_ae_analyst",
    "export_da_analyst",
    "export_ae_analyst",
)


class ScopeBulkAssignmentSummaryQuerySchema(Schema):
    groupBy = fields.String(
        required=True,
        validate=validate.OneOf(BULK_ASSIGNMENT_GROUPS),
    )


class ScopeBulkAssignmentScopesQuerySchema(Schema):
    groupBy = fields.String(
        required=True,
        validate=validate.OneOf(BULK_ASSIGNMENT_GROUPS),
    )
    userId = UUIDStringField(required=True)


class ScopeBulkAssignmentUpdatePayloadSchema(Schema):
    groupBy = fields.String(
        required=True,
        validate=validate.OneOf(BULK_ASSIGNMENT_GROUPS),
    )
    fromUserId = UUIDStringField(required=True)
    toUserId = UUIDStringField(required=True)
    scopeIds = fields.List(UUIDStringField(), required=True, validate=validate.Length(min=1))

    @validates_schema
    def validate_users(self, data, **kwargs):
        if data.get("fromUserId") == data.get("toUserId"):
            raise ValidationError("fromUserId and toUserId must be different.", field_name="toUserId")
