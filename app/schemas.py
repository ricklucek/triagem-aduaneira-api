from marshmallow import Schema, fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from .models import Scope, ScopeVersion, User


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash", "created_at")


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class RefreshSchema(Schema):
    refreshToken = fields.String(required=True)


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

class CreateAdminSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)