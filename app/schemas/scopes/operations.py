from marshmallow import Schema, fields, validates_schema, ValidationError

from app.models.enums import (
    DestinationPurpose,
    LocationType,
    OperationType,
)
from app.schemas.common import EnumField, UUIDStringField


class ScopeOperationNcmSchema(Schema):
    id = UUIDStringField(dump_only=True)
    code = fields.String(required=True)
    description = fields.String(allow_none=True)


class ScopeOperationLocationSchema(Schema):
    id = UUIDStringField(dump_only=True)
    type = EnumField(LocationType, attribute="location_type")
    code = fields.String(allow_none=True)
    name = fields.String(required=True)
    rawValue = fields.String(attribute="raw_value", allow_none=True)


class ScopeOperationAuthoritySchema(Schema):
    id = UUIDStringField(dump_only=True)
    code = fields.String(allow_none=True)
    name = fields.String(required=True)


class ScopeOperationDestinationPurposeSchema(Schema):
    id = UUIDStringField(dump_only=True)
    purpose = EnumField(DestinationPurpose)
    consumptionSubtype = fields.String(attribute="consumption_subtype", allow_none=True)


class ScopeOperationDetailSchema(Schema):
    id = UUIDStringField(dump_only=True)
    operationType = EnumField(OperationType, attribute="operation_type")

    productsDescription = fields.String(attribute="products_description", allow_none=True)
    ncmNotes = fields.String(attribute="ncm_notes", allow_none=True)

    hasExporterRelationship = fields.Boolean(attribute="has_exporter_relationship", allow_none=True)
    requiresDtc = fields.Boolean(attribute="requires_dtc", allow_none=True)
    requiresDta = fields.Boolean(attribute="requires_dta", allow_none=True)
    requiresLiLpco = fields.Boolean(attribute="requires_li_lpco", allow_none=True)

    otherAuthority = fields.String(attribute="other_authority", allow_none=True)

    ncms = fields.Nested(ScopeOperationNcmSchema, many=True)
    entryLocations = fields.Method("get_entry_locations")
    customsClearanceLocations = fields.Method("get_customs_clearance_locations")
    authorities = fields.Nested(ScopeOperationAuthoritySchema, many=True)
    destinationPurposes = fields.Nested(
        ScopeOperationDestinationPurposeSchema,
        attribute="destination_purposes",
        many=True,
    )

    location_schema = ScopeOperationLocationSchema()

    def get_entry_locations(self, obj):
        return [
            self.location_schema.dump(item)
            for item in obj.locations
            if str(item.location_type) == LocationType.ENTRY.value
        ]

    def get_customs_clearance_locations(self, obj):
        return [
            self.location_schema.dump(item)
            for item in obj.locations
            if str(item.location_type) == LocationType.CUSTOMS_CLEARANCE.value
        ]


class ScopeOperationsSchema(Schema):
    types = fields.Method("get_types")
    importOperation = fields.Method("get_import_operation")
    exportOperation = fields.Method("get_export_operation")

    operation_schema = ScopeOperationDetailSchema()

    def get_types(self, scope):
        profile = scope.operation_profile
        if not profile:
            return []

        values = []
        if profile.has_import:
            values.append(OperationType.IMPORT.value)
        if profile.has_export:
            values.append(OperationType.EXPORT.value)
        return values

    def get_import_operation(self, scope):
        if not scope.import_operation:
            return None
        return self.operation_schema.dump(scope.import_operation)

    def get_export_operation(self, scope):
        if not scope.export_operation:
            return None
        return self.operation_schema.dump(scope.export_operation)


class ScopeOperationNcmPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    code = fields.String(required=True)
    description = fields.String(allow_none=True, load_default=None)


class ScopeOperationLocationPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    code = fields.String(allow_none=True, load_default=None)
    name = fields.String(required=True)
    rawValue = fields.String(attribute="raw_value", allow_none=True, load_default=None)


class ScopeOperationAuthorityPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    code = fields.String(allow_none=True, load_default=None)
    name = fields.String(required=True)


class ScopeOperationDestinationPurposePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    purpose = EnumField(DestinationPurpose, required=True)
    consumptionSubtype = fields.String(attribute="consumption_subtype", allow_none=True, load_default=None)


class ScopeOperationPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)

    productsDescription = fields.String(attribute="products_description", allow_none=True, load_default=None)
    ncmNotes = fields.String(attribute="ncm_notes", allow_none=True, load_default=None)

    hasExporterRelationship = fields.Boolean(attribute="has_exporter_relationship", allow_none=True, load_default=None)
    requiresDtc = fields.Boolean(attribute="requires_dtc", allow_none=True, load_default=None)
    requiresDta = fields.Boolean(attribute="requires_dta", allow_none=True, load_default=None)
    requiresLiLpco = fields.Boolean(attribute="requires_li_lpco", allow_none=True, load_default=None)

    otherAuthority = fields.String(attribute="other_authority", allow_none=True, load_default=None)

    ncms = fields.List(fields.Nested(ScopeOperationNcmPayloadSchema), load_default=[])
    entryLocations = fields.List(fields.Nested(ScopeOperationLocationPayloadSchema), load_default=[])
    customsClearanceLocations = fields.List(fields.Nested(ScopeOperationLocationPayloadSchema), load_default=[])
    authorities = fields.List(fields.Nested(ScopeOperationAuthorityPayloadSchema), load_default=[])
    destinationPurposes = fields.List(fields.Nested(ScopeOperationDestinationPurposePayloadSchema), load_default=[])


class ScopeOperationsPayloadSchema(Schema):
    types = fields.List(EnumField(OperationType), load_default=[])
    importOperation = fields.Nested(ScopeOperationPayloadSchema, allow_none=True, load_default=None)
    exportOperation = fields.Nested(ScopeOperationPayloadSchema, allow_none=True, load_default=None)

    @validates_schema
    def validate_operation_payloads(self, data, **kwargs):
        operation_types = set(data.get("types") or [])

        if OperationType.IMPORT in operation_types and not data.get("importOperation"):
            raise ValidationError("importOperation is required when types contains IMPORT.", field_name="importOperation")

        if OperationType.EXPORT in operation_types and not data.get("exportOperation"):
            raise ValidationError("exportOperation is required when types contains EXPORT.", field_name="exportOperation")
