from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    Preposto,
    PrepostoContact,
    PrepostoLocation,
    ScopePreposto,
)
from app.models.enums import OperationType
from .common import EnumField, UUIDStringField


class PrepostoContactSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    prepostoId = UUIDStringField(attribute="preposto_id", dump_only=True)

    class Meta:
        model = PrepostoContact
        load_instance = True
        include_fk = True
        exclude = ("preposto_id",)


class PrepostoLocationSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    prepostoId = UUIDStringField(attribute="preposto_id", dump_only=True)
    placeDescription = fields.String(attribute="place_description", allow_none=True)
    placeType = fields.String(attribute="place_type", allow_none=True)
    servesImport = fields.Boolean(attribute="serves_import")
    servesExport = fields.Boolean(attribute="serves_export")
    importAmount = fields.Decimal(attribute="import_amount", as_string=False, allow_none=True)
    exportAmount = fields.Decimal(attribute="export_amount", as_string=False, allow_none=True)
    importAmountDescription = fields.String(attribute="import_amount_description", allow_none=True)
    exportAmountDescription = fields.String(attribute="export_amount_description", allow_none=True)

    class Meta:
        model = PrepostoLocation
        load_instance = True
        include_fk = True
        exclude = (
            "preposto_id",
            "place_description",
            "place_type",
            "serves_import",
            "serves_export",
            "import_amount",
            "export_amount",
            "import_amount_description",
            "export_amount_description",
        )


class PrepostoSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    organizationId = UUIDStringField(attribute="organization_id", dump_only=True)
    legalName = fields.String(attribute="legal_name", allow_none=True)
    contacts = fields.Nested(PrepostoContactSchema, many=True, dump_only=True)
    locations = fields.Nested(PrepostoLocationSchema, many=True, dump_only=True)

    class Meta:
        model = Preposto
        load_instance = True
        include_fk = True
        exclude = ("organization_id", "legal_name", "scope_links")


class ScopePrepostoCitySchema(Schema):
    id = UUIDStringField(dump_only=True)
    city = fields.String(required=True)
    state = fields.String(allow_none=True)


class ScopePrepostoSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    scopeId = UUIDStringField(attribute="scope_id", dump_only=True)
    prepostoId = UUIDStringField(attribute="preposto_id", dump_only=True)
    operationType = EnumField(OperationType, attribute="operation_type")
    includedInCascoCustomsClearance = fields.Boolean(
        attribute="included_in_casco_customs_clearance",
        allow_none=True,
    )
    otherPort = fields.String(attribute="other_port", allow_none=True)
    otherBorder = fields.String(attribute="other_border", allow_none=True)
    preposto = fields.Nested(PrepostoSchema, dump_only=True)
    cities = fields.Nested(ScopePrepostoCitySchema, many=True, dump_only=True)

    class Meta:
        model = ScopePreposto
        load_instance = True
        include_fk = True
        exclude = (
            "scope_id",
            "preposto_id",
            "operation_type",
            "included_in_casco_customs_clearance",
            "other_port",
            "other_border",
        )


class PrepostoContactPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    name = fields.String(required=True)
    email = fields.Email(allow_none=True, load_default=None)
    phone = fields.String(allow_none=True, load_default=None)
    whatsapp = fields.String(allow_none=True, load_default=None)
    primary = fields.Boolean(load_default=False)


class PrepostoLocationPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    city = fields.String(required=True)
    state = fields.String(allow_none=True, load_default=None)
    placeDescription = fields.String(attribute="place_description", allow_none=True, load_default=None)
    placeType = fields.String(attribute="place_type", allow_none=True, load_default=None)
    servesImport = fields.Boolean(attribute="serves_import", load_default=False)
    servesExport = fields.Boolean(attribute="serves_export", load_default=False)
    importAmount = fields.Decimal(attribute="import_amount", as_string=False, allow_none=True, load_default=None)
    exportAmount = fields.Decimal(attribute="export_amount", as_string=False, allow_none=True, load_default=None)
    importAmountDescription = fields.String(attribute="import_amount_description", allow_none=True, load_default=None)
    exportAmountDescription = fields.String(attribute="export_amount_description", allow_none=True, load_default=None)
    currency = fields.String(load_default="BRL")
    notes = fields.String(allow_none=True, load_default=None)


class PrepostoPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    name = fields.String(required=True)
    legalName = fields.String(attribute="legal_name", allow_none=True, load_default=None)
    active = fields.Boolean(load_default=True)
    notes = fields.String(allow_none=True, load_default=None)
    contacts = fields.List(fields.Nested(PrepostoContactPayloadSchema), load_default=[])
    locations = fields.List(fields.Nested(PrepostoLocationPayloadSchema), load_default=[])
