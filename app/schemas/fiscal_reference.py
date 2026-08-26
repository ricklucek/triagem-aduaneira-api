from datetime import date

from marshmallow import Schema, fields, validate, validates, ValidationError


class FiscalMunicipalitySchema(Schema):
    code = fields.String(required=True)
    name = fields.String(required=True)
    state = fields.String(required=True)
    active = fields.Boolean(required=True)
    updated_at = fields.DateTime(required=True)


class FiscalCountrySchema(Schema):
    bacen_code = fields.String(required=True)
    iso_alpha_2 = fields.String(allow_none=True)
    iso_alpha_3 = fields.String(allow_none=True)
    name = fields.String(required=True)
    valid_from = fields.Date(allow_none=True)
    valid_until = fields.Date(allow_none=True)
    active = fields.Boolean(required=True)
    updated_at = fields.DateTime(required=True)


class MunicipalityReferenceQuerySchema(Schema):
    q = fields.String(load_default="", validate=validate.Length(max=120))
    state = fields.String(load_default=None, allow_none=True, validate=validate.Length(equal=2))
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=50))

    @validates("state")
    def validate_state(self, value: str, **kwargs):
        if value and not value.isalpha():
            raise ValidationError("Informe a UF com duas letras.")


class CountryReferenceQuerySchema(Schema):
    q = fields.String(load_default="", validate=validate.Length(max=120))
    active_on = fields.Date(load_default=date.today)
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=50))
