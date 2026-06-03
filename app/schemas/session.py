from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class RegisterSchema(Schema):
    nome = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=8))
    role = fields.String(load_default="admin")
    setor = fields.String(allow_none=True)

    organization_id = fields.String(load_default=None, allow_none=True)
    organization_nome = fields.String(load_default=None, allow_none=True)
    organization_slug = fields.String(load_default=None, allow_none=True)
    organization_cnpj = fields.String(load_default=None, allow_none=True)

    @validates_schema
    def validate_org(self, data, **kwargs):
        if not data.get("organization_id") and not data.get("organization_nome"):
            raise ValidationError(
                "Informe organization_id existente ou organization_nome para criar organização.",
                field_name="organization_id",
            )


class RefreshSchema(Schema):
    refreshToken = fields.String(required=True)