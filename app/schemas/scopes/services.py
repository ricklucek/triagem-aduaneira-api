from marshmallow import Schema, fields, validates_schema, ValidationError

from app.models.enums import (
    OperationType,
    PricingType,
    ServiceDetailType,
    ServiceOperationType,
    ServiceType,
)
from app.schemas.common import EnumField, UUIDStringField
from app.schemas.identity import UserSummarySchema
from app.schemas.prepostos import ScopePrepostoSchema


class ScopeServiceFreightDetailSchema(Schema):
    id = UUIDStringField(dump_only=True)
    mode = fields.String(allow_none=True)
    negotiatedPtax = fields.Decimal(attribute="negotiated_ptax", as_string=False, allow_none=True)
    generalNotes = fields.String(attribute="general_notes", allow_none=True)


class ScopeServiceInsuranceDetailSchema(Schema):
    id = UUIDStringField(dump_only=True)
    minimumAmount = fields.Decimal(attribute="minimum_amount", as_string=False, allow_none=True)
    cfrPercentage = fields.Decimal(attribute="cfr_percentage", as_string=False, allow_none=True)
    policyInclusionDate = fields.Date(attribute="policy_inclusion_date", allow_none=True)
    additionalDescription = fields.String(attribute="additional_description", allow_none=True)


class ScopeServiceCustomsBrokerDetailSchema(Schema):
    id = UUIDStringField(dump_only=True)
    salaryMultiplier = fields.Decimal(attribute="salary_multiplier", as_string=False, allow_none=True)
    pricingReference = fields.String(attribute="pricing_reference", allow_none=True)


class ScopeServiceCertificateDetailSchema(Schema):
    id = UUIDStringField(dump_only=True)
    certificateName = fields.String(attribute="certificate_name", allow_none=True)
    issuingAuthority = fields.String(attribute="issuing_authority", allow_none=True)
    notes = fields.String(allow_none=True)


class ScopeServiceSchema(Schema):
    id = UUIDStringField(dump_only=True)
    catalogId = UUIDStringField(attribute="service_catalog_id")
    code = fields.Method("get_code")
    name = fields.Method("get_name")
    serviceType = fields.Method("get_service_type")
    operationType = EnumField(ServiceOperationType, attribute="operation_type")
    enabled = fields.Boolean()
    pricingType = EnumField(PricingType, attribute="pricing_type", allow_none=True)
    amount = fields.Decimal(as_string=False, allow_none=True)
    currency = fields.String()
    responsibleUser = fields.Nested(UserSummarySchema, attribute="responsible_user", allow_none=True)
    lastUpdatedOn = fields.Date(attribute="last_updated_on", allow_none=True)
    notes = fields.String(allow_none=True)

    details = fields.Method("get_details")

    def get_code(self, obj):
        return obj.service_catalog.code if obj.service_catalog else None

    def get_name(self, obj):
        return obj.service_catalog.name if obj.service_catalog else None

    def get_service_type(self, obj):
        if not obj.service_catalog:
            return None
        return str(obj.service_catalog.service_type)

    def get_details(self, obj):
        if obj.freight_detail:
            return {
                "type": ServiceDetailType.FREIGHT.value,
                **ScopeServiceFreightDetailSchema().dump(obj.freight_detail),
            }

        if obj.insurance_detail:
            return {
                "type": ServiceDetailType.INSURANCE.value,
                **ScopeServiceInsuranceDetailSchema().dump(obj.insurance_detail),
            }

        if obj.customs_broker_detail:
            return {
                "type": ServiceDetailType.CUSTOMS_BROKER.value,
                **ScopeServiceCustomsBrokerDetailSchema().dump(obj.customs_broker_detail),
            }

        if obj.certificate_detail:
            return {
                "type": ServiceDetailType.CERTIFICATE.value,
                **ScopeServiceCertificateDetailSchema().dump(obj.certificate_detail),
            }

        return None


class ScopeServicesSchema(Schema):
    items = fields.Method("get_items")
    prepostos = fields.Method("get_prepostos")

    service_schema = ScopeServiceSchema(many=True)
    preposto_schema = ScopePrepostoSchema(many=True)

    def get_items(self, scope):
        return self.service_schema.dump([service for service in scope.services if service.enabled])

    def get_prepostos(self, scope):
        return self.preposto_schema.dump([preposto for preposto in scope.prepostos if preposto.enabled])


class ScopeServiceFreightDetailPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    mode = fields.String(allow_none=True, load_default=None)
    negotiatedPtax = fields.Decimal(attribute="negotiated_ptax", as_string=False, allow_none=True, load_default=None)
    generalNotes = fields.String(attribute="general_notes", allow_none=True, load_default=None)


class ScopeServiceInsuranceDetailPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    minimumAmount = fields.Decimal(attribute="minimum_amount", as_string=False, allow_none=True, load_default=None)
    cfrPercentage = fields.Decimal(attribute="cfr_percentage", as_string=False, allow_none=True, load_default=None)
    policyInclusionDate = fields.Date(attribute="policy_inclusion_date", allow_none=True, load_default=None)
    additionalDescription = fields.String(attribute="additional_description", allow_none=True, load_default=None)


class ScopeServiceCustomsBrokerDetailPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    salaryMultiplier = fields.Decimal(attribute="salary_multiplier", as_string=False, allow_none=True, load_default=None)
    pricingReference = fields.String(attribute="pricing_reference", allow_none=True, load_default=None)


class ScopeServiceCertificateDetailPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    certificateName = fields.String(attribute="certificate_name", allow_none=True, load_default=None)
    issuingAuthority = fields.String(attribute="issuing_authority", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)


class ScopeServiceDetailPayloadSchema(Schema):
    type = EnumField(ServiceDetailType, required=True)
    freight = fields.Nested(ScopeServiceFreightDetailPayloadSchema, allow_none=True, load_default=None)
    insurance = fields.Nested(ScopeServiceInsuranceDetailPayloadSchema, allow_none=True, load_default=None)
    customsBroker = fields.Nested(ScopeServiceCustomsBrokerDetailPayloadSchema, allow_none=True, load_default=None)
    certificate = fields.Nested(ScopeServiceCertificateDetailPayloadSchema, allow_none=True, load_default=None)

    @validates_schema
    def validate_detail(self, data, **kwargs):
        detail_type = data.get("type")
        required_by_type = {
            ServiceDetailType.FREIGHT: "freight",
            ServiceDetailType.INSURANCE: "insurance",
            ServiceDetailType.CUSTOMS_BROKER: "customsBroker",
            ServiceDetailType.CERTIFICATE: "certificate",
        }

        required_key = required_by_type.get(detail_type)
        if required_key and not data.get(required_key):
            raise ValidationError(f"{required_key} is required for detail type {detail_type.value}.", field_name=required_key)


class ScopeServicePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    serviceCatalogId = UUIDStringField(attribute="service_catalog_id", required=True)
    operationType = EnumField(ServiceOperationType, attribute="operation_type", required=True)

    enabled = fields.Boolean(load_default=True)
    pricingType = EnumField(PricingType, attribute="pricing_type", allow_none=True, load_default=None)
    amount = fields.Decimal(as_string=False, allow_none=True, load_default=None)
    currency = fields.String(load_default="BRL")

    responsibleUserId = UUIDStringField(attribute="responsible_user_id", allow_none=True, load_default=None)
    lastUpdatedOn = fields.Date(attribute="last_updated_on", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)

    details = fields.Nested(ScopeServiceDetailPayloadSchema, allow_none=True, load_default=None)


class ScopePrepostoCityPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    city = fields.String(required=True)
    state = fields.String(allow_none=True, load_default=None)


class ScopePrepostoPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    prepostoId = UUIDStringField(attribute="preposto_id", required=True)
    operationType = EnumField(OperationType, attribute="operation_type", required=True)
    enabled = fields.Boolean(load_default=True)
    amount = fields.Decimal(as_string=False, allow_none=True, load_default=None)
    includedInCascoCustomsClearance = fields.Boolean(
        attribute="included_in_casco_customs_clearance",
        allow_none=True,
        load_default=None,
    )
    otherPort = fields.String(attribute="other_port", allow_none=True, load_default=None)
    otherBorder = fields.String(attribute="other_border", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)
    cities = fields.List(fields.Nested(ScopePrepostoCityPayloadSchema), load_default=[])


class ScopeServicesPayloadSchema(Schema):
    items = fields.List(fields.Nested(ScopeServicePayloadSchema), load_default=[])
    prepostos = fields.List(fields.Nested(ScopePrepostoPayloadSchema), load_default=[])
