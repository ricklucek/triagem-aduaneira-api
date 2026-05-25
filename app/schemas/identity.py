from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import AdminProfile, Organization, User
from .common import DateTimeMixinSchema, UUIDStringField


class OrganizationSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)

    class Meta:
        model = Organization
        load_instance = True
        include_fk = True


class UserSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    organizationId = UUIDStringField(attribute="organization_id", allow_none=True)
    name = fields.String(required=True)
    email = fields.Email(required=True)
    role = fields.String(required=True)
    department = fields.String(allow_none=True)
    active = fields.Boolean()

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ("password_hash", "organization_id", "assigned_scopes", "admin_profile")


class UserSummarySchema(Schema):
    id = UUIDStringField(dump_only=True)
    name = fields.String(required=True)
    email = fields.Email(required=True)
    systemRole = fields.String(attribute="role", allow_none=True)
    department = fields.String(allow_none=True)
    active = fields.Boolean()


class AdminProfileSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    userId = UUIDStringField(attribute="user_id", allow_none=True)

    class Meta:
        model = AdminProfile
        load_instance = True
        include_fk = True
        exclude = ("user_id",)
