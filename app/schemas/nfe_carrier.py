from marshmallow import Schema, ValidationError, fields, pre_load, validate, validates_schema


def _digits(value) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


class NfeCarrierSchema(Schema):
    id = fields.UUID(dump_only=True)
    organization_id = fields.UUID(dump_only=True)
    legal_name = fields.String(required=True)
    trade_name = fields.String(allow_none=True)
    tax_id = fields.String(required=True)
    state_registration = fields.String(allow_none=True)
    street = fields.String(required=True)
    number = fields.String(required=True)
    complement = fields.String(allow_none=True)
    district = fields.String(required=True)
    municipality_code = fields.String(required=True)
    municipality_name = fields.String(required=True)
    state = fields.String(required=True)
    zip_code = fields.String(required=True)
    phone = fields.String(allow_none=True)
    email = fields.Email(allow_none=True)
    active = fields.Boolean(required=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)


class NfeCarrierPayloadSchema(Schema):
    legal_name = fields.String(validate=validate.Length(min=2, max=60))
    trade_name = fields.String(allow_none=True, validate=validate.Length(max=60))
    tax_id = fields.String()
    state_registration = fields.String(allow_none=True, validate=validate.Length(max=30))
    street = fields.String(validate=validate.Length(min=1, max=255))
    number = fields.String(validate=validate.Length(min=1, max=60))
    complement = fields.String(allow_none=True, validate=validate.Length(max=255))
    district = fields.String(validate=validate.Length(min=1, max=120))
    municipality_code = fields.String()
    zip_code = fields.String()
    phone = fields.String(allow_none=True, validate=validate.Length(max=20))
    email = fields.Email(allow_none=True, validate=validate.Length(max=255))
    active = fields.Boolean()

    @pre_load
    def normalize_payload(self, data, **kwargs):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        for field_name in (
            "legal_name",
            "trade_name",
            "state_registration",
            "street",
            "number",
            "complement",
            "district",
            "phone",
            "email",
        ):
            if field_name in normalized and isinstance(normalized[field_name], str):
                normalized[field_name] = normalized[field_name].strip() or None
        for field_name in ("tax_id", "municipality_code", "zip_code"):
            if field_name in normalized:
                normalized[field_name] = _digits(normalized[field_name])
        return normalized

    @validates_schema
    def validate_payload(self, data, **kwargs):
        errors = {}
        tax_id = data.get("tax_id")
        if tax_id is not None and len(tax_id) not in (11, 14):
            errors["tax_id"] = ["Informe um CPF com 11 dígitos ou CNPJ com 14 dígitos."]
        municipality_code = data.get("municipality_code")
        if municipality_code is not None and len(municipality_code) != 7:
            errors["municipality_code"] = ["O código IBGE deve conter 7 dígitos."]
        zip_code = data.get("zip_code")
        if zip_code is not None and len(zip_code) != 8:
            errors["zip_code"] = ["O CEP deve conter 8 dígitos."]
        if errors:
            raise ValidationError(errors)


class CreateNfeCarrierSchema(NfeCarrierPayloadSchema):
    legal_name = fields.String(required=True, validate=validate.Length(min=2, max=60))
    tax_id = fields.String(required=True)
    street = fields.String(required=True, validate=validate.Length(min=1, max=255))
    number = fields.String(required=True, validate=validate.Length(min=1, max=60))
    district = fields.String(required=True, validate=validate.Length(min=1, max=120))
    municipality_code = fields.String(required=True)
    zip_code = fields.String(required=True)
    active = fields.Boolean(load_default=True)


class UpdateNfeCarrierSchema(NfeCarrierPayloadSchema):
    pass


class NfeCarrierListQuerySchema(Schema):
    q = fields.String(load_default="", validate=validate.Length(max=120))
    active = fields.Boolean(load_default=None, allow_none=True)
    limit = fields.Integer(load_default=25, validate=validate.Range(min=1, max=100))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))
