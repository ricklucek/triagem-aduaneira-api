from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    User,
)
from app.services.user_tags import serialize_user_tag, tags_for_user

class UserSchema(SQLAlchemyAutoSchema):
    tags = fields.Method("get_tags", dump_only=True)

    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash",)

    @staticmethod
    def get_tags(user):
        return [serialize_user_tag(tag) for tag in tags_for_user(user)]
