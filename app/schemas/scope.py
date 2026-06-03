from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    Scope,
    ScopeAssignment,
    ScopeService,
    ScopeVersion,
)
from app.schemas.client import ClientSchema
from app.schemas.user import UserSchema


class ScopeAssignmentSchema(SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, only=("id", "nome", "email", "role", "setor"), dump_only=True)

    class Meta:
        model = ScopeAssignment
        load_instance = True
        include_fk = True


class ScopeServiceSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ScopeService
        load_instance = True
        include_fk = True


class ScopeVersionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ScopeVersion
        load_instance = True
        include_fk = True


class ScopeSchema(SQLAlchemyAutoSchema):
    client = fields.Nested(ClientSchema, dump_only=True)
    responsible_user = fields.Nested(UserSchema, only=("id", "nome", "email", "role", "setor"), dump_only=True)
    assignments = fields.Nested(ScopeAssignmentSchema, many=True, dump_only=True)
    services = fields.Nested(ScopeServiceSchema, many=True, dump_only=True)

    class Meta:
        model = Scope
        load_instance = True
        include_fk = True


class ScopeSummarySchema(Schema):
    id = fields.String(required=True)
    status = fields.String(required=True)
    version = fields.Integer(allow_none=True)
    updated_at = fields.DateTime(allow_none=True)
    last_published_at = fields.DateTime(allow_none=True)
    client_id = fields.String(allow_none=True)
    client_cnpj = fields.String(allow_none=True)
    client_razao_social = fields.String(allow_none=True)
    responsible_user_id = fields.String(allow_none=True)
    responsible_user_nome = fields.String(allow_none=True)


class ScopeListQuerySchema(Schema):
    status = fields.String(required=False)
    q = fields.String(required=False)
    cnpj = fields.String(required=False)
    client_id = fields.String(required=False)
    assigned_user_id = fields.String(required=False)
    responsible_user_id = fields.String(required=False)
    created_by_id = fields.String(required=False)
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))


class ScopeBulkResponsibleSchema(Schema):
    old_user_id = fields.String(required=True)
    new_user_id = fields.String(required=True)
    apply_status = fields.List(fields.String(), load_default=[])
    only_active_assignments = fields.Boolean(load_default=True)
    dry_run = fields.Boolean(load_default=True)