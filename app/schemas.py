from marshmallow import Schema, fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from .models import Admin, Scope, ScopeVersion, User


class AdminSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Admin
        load_instance = True
        exclude = ("password_hash", "created_at")


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash", "created_at")


class AuthIdentitySchema(Schema):
    id = fields.String(required=True)
    nome = fields.String(required=True)
    email = fields.Email(required=True)
    role = fields.String(required=True)
    setor = fields.String(allow_none=True)
    tipo = fields.String(required=True)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class RefreshSchema(Schema):
    refreshToken = fields.String(required=True)


class CreateAdminSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    nome = fields.String(load_default="Administrador")


class AdminSettingsSchema(Schema):
    salarioMinimoVigente = fields.Decimal(as_string=False, required=True)
    dadosBancariosCasco = fields.Dict(required=True)


class ScopeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Scope
        load_instance = True
        include_fk = True


class ScopeSummarySchema(Schema):
    id = fields.String(required=True)
    cnpj = fields.String(allow_none=True)
    razao_social = fields.String(allow_none=True)
    status = fields.String(required=True)
    updated_at = fields.DateTime(allow_none=True)
    last_published_at = fields.DateTime(allow_none=True)
    version_count = fields.Integer(required=True)
    completeness_score = fields.Integer(required=True)


class ScopeVersionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ScopeVersion
        load_instance = True
        include_fk = True
