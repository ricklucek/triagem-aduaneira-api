from enum import Enum

from sqlalchemy import Enum as SAEnum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


def enum_column(enum_class: type[Enum], name: str, **kwargs):
    return SAEnum(
        enum_class,
        values_callable=lambda enum: [item.value for item in enum],
        name=name,
        native_enum=False,
        validate_strings=True,
        **kwargs,
    )


class ScopeStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class OperationType(StrEnum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class ServiceOperationType(StrEnum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    BOTH = "BOTH"


class AssignmentRole(StrEnum):
    COMMERCIAL_RESPONSIBLE = "COMMERCIAL_RESPONSIBLE"
    IMPORT_DA_ANALYST = "IMPORT_DA_ANALYST"
    IMPORT_AE_ANALYST = "IMPORT_AE_ANALYST"
    EXPORT_DA_ANALYST = "EXPORT_DA_ANALYST"
    EXPORT_AE_ANALYST = "EXPORT_AE_ANALYST"


class LocationType(StrEnum):
    ENTRY = "ENTRY"
    CUSTOMS_CLEARANCE = "CUSTOMS_CLEARANCE"


class DestinationPurpose(StrEnum):
    RESALE = "RESALE"
    INDUSTRIALIZATION = "INDUSTRIALIZATION"
    USE_AND_CONSUMPTION = "USE_AND_CONSUMPTION"
    FIXED_ASSET = "FIXED_ASSET"


class TaxRegime(StrEnum):
    FULL = "FULL"
    EXEMPTION = "EXEMPTION"
    SUSPENSION = "SUSPENSION"
    REDUCTION = "REDUCTION"
    OTHER = "OTHER"


class AccountOwnerType(StrEnum):
    CASCO = "CASCO"
    CLIENT = "CLIENT"


class PaymentPreference(StrEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    PIX = "PIX"
    BANK_SLIP = "BANK_SLIP"
    OTHER = "OTHER"


class PricingType(StrEnum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    MINIMUM_AMOUNT = "MINIMUM_AMOUNT"
    SALARY_BASED = "SALARY_BASED"
    CASE_BY_CASE = "CASE_BY_CASE"
    INCLUDED = "INCLUDED"
    OTHER = "OTHER"


class ServiceType(StrEnum):
    CUSTOMS_CLEARANCE = "CUSTOMS_CLEARANCE"
    PREPOSTO = "PREPOSTO"
    LI_LPCO_ISSUANCE = "LI_LPCO_ISSUANCE"
    PRODUCT_CATALOG_REGISTRATION = "PRODUCT_CATALOG_REGISTRATION"
    CONSULTING = "CONSULTING"
    INTERNATIONAL_FREIGHT = "INTERNATIONAL_FREIGHT"
    INTERNATIONAL_INSURANCE = "INTERNATIONAL_INSURANCE"
    ROAD_FREIGHT = "ROAD_FREIGHT"
    NFE_ISSUANCE = "NFE_ISSUANCE"
    ORIGIN_CERTIFICATE = "ORIGIN_CERTIFICATE"
    PHYTOSANITARY_CERTIFICATE = "PHYTOSANITARY_CERTIFICATE"
    OTHER_CERTIFICATE = "OTHER_CERTIFICATE"
    SPECIAL_REGIME = "SPECIAL_REGIME"
    OTHER = "OTHER"


class ServiceDetailType(StrEnum):
    FREIGHT = "FREIGHT"
    INSURANCE = "INSURANCE"
    CUSTOMS_BROKER = "CUSTOMS_BROKER"
    CERTIFICATE = "CERTIFICATE"
