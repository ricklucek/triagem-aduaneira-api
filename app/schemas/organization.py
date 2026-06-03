from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    Organization,
)


class OrganizationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Organization
        load_instance = True
        exclude = ("created_at", "updated_at")

class OrganizationFixedInfoSchema(Schema):
    salarioMinimoVigente = fields.Decimal(as_string=False, required=True)
    dadosBancariosCasco = fields.Dict(required=True)