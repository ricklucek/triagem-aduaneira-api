from marshmallow import Schema, fields

from app.models.enums import AccountOwnerType, DestinationPurpose, TaxRegime
from app.schemas.common import EnumField, UUIDStringField


class FederalTaxProfileSchema(Schema):
    id = UUIDStringField(dump_only=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type")
    bankName = fields.String(attribute="bank_name", allow_none=True)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True)
    bankAccount = fields.String(attribute="bank_account", allow_none=True)

    iiRegime = EnumField(TaxRegime, attribute="ii_regime", allow_none=True)
    iiBenefitDetail = fields.String(attribute="ii_benefit_detail", allow_none=True)
    ipiRegime = EnumField(TaxRegime, attribute="ipi_regime", allow_none=True)
    ipiBenefitDetail = fields.String(attribute="ipi_benefit_detail", allow_none=True)
    pisRegime = EnumField(TaxRegime, attribute="pis_regime", allow_none=True)
    pisBenefitDetail = fields.String(attribute="pis_benefit_detail", allow_none=True)
    cofinsRegime = EnumField(TaxRegime, attribute="cofins_regime", allow_none=True)
    cofinsBenefitDetail = fields.String(attribute="cofins_benefit_detail", allow_none=True)
    notes = fields.String(allow_none=True)


class AfrmmProfileSchema(Schema):
    id = UUIDStringField(dump_only=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type")
    bankName = fields.String(attribute="bank_name", allow_none=True)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True)
    bankAccount = fields.String(attribute="bank_account", allow_none=True)
    regime = EnumField(TaxRegime, allow_none=True)
    benefitDetail = fields.String(attribute="benefit_detail", allow_none=True)
    notes = fields.String(allow_none=True)


class IcmsDestinationRateSchema(Schema):
    id = UUIDStringField(dump_only=True)
    destinationPurpose = EnumField(DestinationPurpose, attribute="destination_purpose")
    collectedRate = fields.Decimal(attribute="collected_rate", as_string=False, allow_none=True)
    effectiveRate = fields.Decimal(attribute="effective_rate", as_string=False, allow_none=True)
    notes = fields.String(allow_none=True)


class IcmsProfileSchema(Schema):
    id = UUIDStringField(dump_only=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type")
    bankName = fields.String(attribute="bank_name", allow_none=True)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True)
    bankAccount = fields.String(attribute="bank_account", allow_none=True)
    regime = EnumField(TaxRegime, allow_none=True)
    collectedRate = fields.Decimal(attribute="collected_rate", as_string=False, allow_none=True)
    effectiveRate = fields.Decimal(attribute="effective_rate", as_string=False, allow_none=True)
    notes = fields.String(allow_none=True)
    destinationRates = fields.Nested(IcmsDestinationRateSchema, attribute="destination_rates", many=True)


class ScopeOperationTaxSchema(Schema):
    federalTaxes = fields.Nested(FederalTaxProfileSchema, attribute="federal_tax_profile", allow_none=True)
    afrmm = fields.Nested(AfrmmProfileSchema, attribute="afrmm_profile", allow_none=True)
    icms = fields.Nested(IcmsProfileSchema, attribute="icms_profile", allow_none=True)


class ScopeTaxesSchema(Schema):
    importTaxes = fields.Method("get_import_taxes")
    exportTaxes = fields.Method("get_export_taxes")

    tax_schema = ScopeOperationTaxSchema()

    def get_import_taxes(self, scope):
        if not scope.import_operation:
            return None
        return self.tax_schema.dump(scope.import_operation)

    def get_export_taxes(self, scope):
        if not scope.export_operation:
            return None
        return self.tax_schema.dump(scope.export_operation)


class FederalTaxProfilePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type", load_default=AccountOwnerType.CASCO)
    bankName = fields.String(attribute="bank_name", allow_none=True, load_default=None)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True, load_default=None)
    bankAccount = fields.String(attribute="bank_account", allow_none=True, load_default=None)

    iiRegime = EnumField(TaxRegime, attribute="ii_regime", allow_none=True, load_default=None)
    iiBenefitDetail = fields.String(attribute="ii_benefit_detail", allow_none=True, load_default=None)
    ipiRegime = EnumField(TaxRegime, attribute="ipi_regime", allow_none=True, load_default=None)
    ipiBenefitDetail = fields.String(attribute="ipi_benefit_detail", allow_none=True, load_default=None)
    pisRegime = EnumField(TaxRegime, attribute="pis_regime", allow_none=True, load_default=None)
    pisBenefitDetail = fields.String(attribute="pis_benefit_detail", allow_none=True, load_default=None)
    cofinsRegime = EnumField(TaxRegime, attribute="cofins_regime", allow_none=True, load_default=None)
    cofinsBenefitDetail = fields.String(attribute="cofins_benefit_detail", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)


class AfrmmProfilePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type", load_default=AccountOwnerType.CASCO)
    bankName = fields.String(attribute="bank_name", allow_none=True, load_default=None)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True, load_default=None)
    bankAccount = fields.String(attribute="bank_account", allow_none=True, load_default=None)
    regime = EnumField(TaxRegime, allow_none=True, load_default=None)
    benefitDetail = fields.String(attribute="benefit_detail", allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)


class IcmsDestinationRatePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    destinationPurpose = EnumField(DestinationPurpose, attribute="destination_purpose", required=True)
    collectedRate = fields.Decimal(attribute="collected_rate", as_string=False, allow_none=True, load_default=None)
    effectiveRate = fields.Decimal(attribute="effective_rate", as_string=False, allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)


class IcmsProfilePayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    paymentAccountType = EnumField(AccountOwnerType, attribute="payment_account_type", load_default=AccountOwnerType.CASCO)
    bankName = fields.String(attribute="bank_name", allow_none=True, load_default=None)
    bankBranch = fields.String(attribute="bank_branch", allow_none=True, load_default=None)
    bankAccount = fields.String(attribute="bank_account", allow_none=True, load_default=None)
    regime = EnumField(TaxRegime, allow_none=True, load_default=None)
    collectedRate = fields.Decimal(attribute="collected_rate", as_string=False, allow_none=True, load_default=None)
    effectiveRate = fields.Decimal(attribute="effective_rate", as_string=False, allow_none=True, load_default=None)
    notes = fields.String(allow_none=True, load_default=None)
    destinationRates = fields.List(fields.Nested(IcmsDestinationRatePayloadSchema), attribute="destination_rates", load_default=[])


class OperationTaxPayloadSchema(Schema):
    federalTaxes = fields.Nested(FederalTaxProfilePayloadSchema, attribute="federal_tax_profile", allow_none=True, load_default=None)
    afrmm = fields.Nested(AfrmmProfilePayloadSchema, attribute="afrmm_profile", allow_none=True, load_default=None)
    icms = fields.Nested(IcmsProfilePayloadSchema, attribute="icms_profile", allow_none=True, load_default=None)


class ScopeTaxesPayloadSchema(Schema):
    importTaxes = fields.Nested(OperationTaxPayloadSchema, allow_none=True, load_default=None)
    exportTaxes = fields.Nested(OperationTaxPayloadSchema, allow_none=True, load_default=None)
