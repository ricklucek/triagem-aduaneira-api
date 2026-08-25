from decimal import Decimal, InvalidOperation

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema

from ..models import FiscalEnvironment, ImportPurpose
from .import_process import (
    NfeAdditionalInfoSchema,
    NfeDocumentOptionsSchema,
    NfeItemDefaultsSchema,
    NfePaymentSchema,
    NfeTransportSchema,
)


class ClientImportTaxRuleSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    id = fields.UUID(dump_only=True)
    organization_id = fields.UUID(dump_only=True)
    client_id = fields.UUID(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=120))
    issuer_state = fields.String(
        required=True,
        validate=validate.Regexp(r"^[A-Z]{2}$"),
    )
    import_purpose = fields.String(
        required=True,
        validate=validate.OneOf(ImportPurpose.values()),
    )
    import_modality = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["direct", "on_behalf", "by_order"]),
    )
    tax_regime = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["1", "2", "3"]),
    )
    ncm_pattern = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Regexp(r"^[0-9]{2,8}$"),
    )
    priority = fields.Integer(load_default=0)
    configuration_json = fields.Dict(required=True)
    additional_cost_defaults = fields.Dict(load_default=None, allow_none=True)
    transport_defaults = fields.Dict(load_default=None, allow_none=True)
    payment_defaults = fields.Dict(load_default=None, allow_none=True)
    active = fields.Boolean(load_default=True)
    effective_from = fields.Date(load_default=None, allow_none=True)
    effective_until = fields.Date(load_default=None, allow_none=True)
    created_by_user_id = fields.UUID(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_rule(self, data, **kwargs):
        start = data.get("effective_from")
        end = data.get("effective_until")
        if start and end and end < start:
            raise ValidationError(
                "effective_until não pode ser anterior a effective_from.",
                field_name="effective_until",
            )

        if data.get("transport_defaults") is not None:
            NfeTransportSchema().load(data["transport_defaults"])
        if data.get("payment_defaults") is not None:
            NfePaymentSchema().load(data["payment_defaults"])

        configuration = data.get("configuration_json")
        if configuration is None:
            return
        nested_defaults = (
            (
                "document_defaults",
                NfeDocumentOptionsSchema(),
            ),
            ("item_defaults", NfeItemDefaultsSchema()),
            ("additional_info_defaults", NfeAdditionalInfoSchema()),
        )
        for field_name, schema in nested_defaults:
            if configuration.get(field_name) is not None:
                try:
                    schema.load(configuration[field_name])
                except ValidationError as exc:
                    raise ValidationError(
                        {field_name: exc.messages},
                        field_name="configuration_json",
                    ) from exc
        cst = str(configuration.get("icms_cst") or "90").zfill(2)
        supported_csts = {"00", "40", "41", "50", "51", "90"}
        if cst not in supported_csts:
            raise ValidationError(
                "configuration_json.icms_cst deve ser 00, 40, 41, 50, 51 ou 90.",
                field_name="configuration_json",
            )
        raw_rate = configuration.get("icms_rate")
        raw_confirmed = configuration.get("icms_tax_treatment_confirmed")
        if raw_confirmed not in (None, True, False):
            raise ValidationError(
                "configuration_json.icms_tax_treatment_confirmed deve ser "
                "booleano.",
                field_name="configuration_json",
            )
        if cst in {"40", "41", "50"}:
            if raw_rate not in (None, ""):
                raise ValidationError(
                    f"ICMS CST {cst} não aceita alíquota nominal.",
                    field_name="configuration_json",
                )
            return
        if raw_rate in (None, "") and cst == "51":
            try:
                base_reduction_rate = Decimal(
                    str(configuration.get("icms_base_reduction_rate"))
                )
            except (InvalidOperation, TypeError, ValueError):
                base_reduction_rate = Decimal("0")
            try:
                deferment_rate = Decimal(
                    str(configuration.get("icms_deferment_rate"))
                )
            except (InvalidOperation, TypeError, ValueError):
                deferment_rate = Decimal("0")
            if (
                deferment_rate != Decimal("100")
                and base_reduction_rate != Decimal("100")
            ):
                raise ValidationError(
                    "ICMS CST 51 sem alíquota nominal somente é aceito para "
                    "XML diagnóstico com diferimento ou redução de base de 100%.",
                    field_name="configuration_json",
                )
            return
        try:
            rate = Decimal(str(raw_rate))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError(
                "configuration_json.icms_rate deve ser numérico.",
                field_name="configuration_json",
            )
        if not Decimal("0") < rate < Decimal("100"):
            raise ValidationError(
                "configuration_json.icms_rate deve ser maior que 0 e menor que 100.",
                field_name="configuration_json",
            )


class UpdateClientImportTaxRuleSchema(ClientImportTaxRuleSchema):
    name = fields.String(validate=validate.Length(min=1, max=120))
    issuer_state = fields.String(validate=validate.Regexp(r"^[A-Z]{2}$"))
    import_purpose = fields.String(validate=validate.OneOf(ImportPurpose.values()))
    configuration_json = fields.Dict()


class NfeContextQuerySchema(Schema):
    duimp_snapshot_id = fields.UUID(load_default=None, allow_none=True)
    import_purpose = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(ImportPurpose.values()),
    )
    provider_environment = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(FiscalEnvironment.values()),
    )
    refresh_external = fields.Boolean(load_default=False)


class ResolveNfeContextSchema(NfeContextQuerySchema):
    refresh_external = fields.Boolean(load_default=True)
    overrides = fields.Dict(load_default=dict)

class NfeItemClassificationQuerySchema(Schema):
    duimp_snapshot_id = fields.UUID(load_default=None, allow_none=True)


class NfeItemClassificationInputSchema(Schema):
    duimp_item_number = fields.String(
        required=True,
        validate=validate.Length(min=1, max=30),
    )
    import_purpose = fields.String(
        required=True,
        validate=validate.OneOf(ImportPurpose.values()),
    )
    tax_rule_id = fields.UUID(load_default=None, allow_none=True)


class BulkNfeItemClassificationSchema(Schema):
    duimp_snapshot_id = fields.UUID(load_default=None, allow_none=True)
    items = fields.List(
        fields.Nested(NfeItemClassificationInputSchema),
        required=True,
        validate=validate.Length(min=1),
    )

    @validates_schema
    def validate_unique_items(self, data, **kwargs):
        numbers = [
            item["duimp_item_number"]
            for item in data.get("items") or []
        ]
        if len(numbers) != len(set(numbers)):
            raise ValidationError(
                "Cada item da DUIMP deve aparecer apenas uma vez.",
                field_name="items",
            )
