from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    Client,
    ClientContact,
)
from app.models.client import ClientFiscalProfile


class ClientContactSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ClientContact
        load_instance = True
        include_fk = True


class ClientSchema(SQLAlchemyAutoSchema):
    contatos = fields.Nested(ClientContactSchema, many=True, dump_only=True)

    class Meta:
        model = Client
        load_instance = True
        include_fk = True

class ClientListQuerySchema(Schema):
    q = fields.String(required=False)
    cnpj = fields.String(required=False)
    ativo = fields.Boolean(required=False)
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=200))
    offset = fields.Integer(load_default=0, validate=validate.Range(min=0))


class ClientUpdateSchema(Schema):
    razao_social = fields.String(required=False)
    nome_resumido = fields.String(allow_none=True, required=False)
    inscricao_estadual = fields.String(allow_none=True, required=False)
    inscricao_municipal = fields.String(allow_none=True, required=False)
    endereco_completo_escritorio = fields.String(allow_none=True, required=False)
    endereco_completo_armazem = fields.String(allow_none=True, required=False)
    cnae_principal = fields.String(allow_none=True, required=False)
    cnae_secundario = fields.String(allow_none=True, required=False)
    regime_tributacao = fields.String(allow_none=True, required=False)
    ativo = fields.Boolean(required=False)

class ClientFiscalProfileSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = ClientFiscalProfile
        load_instance = False
        include_fk = True

    id = fields.UUID(dump_only=True)
    organization_id = fields.UUID(dump_only=True)
    client_id = fields.UUID(required=True)

    legal_name = fields.String(required=True)
    trade_name = fields.String(allow_none=True)

    cnpj = fields.String(required=True)
    state_registration = fields.String(allow_none=True)

    tax_regime = fields.String(
        required=True,
        validate=validate.OneOf(["1", "2", "3"]),
    )

    street = fields.String(required=True)
    number = fields.String(required=True)
    complement = fields.String(allow_none=True)
    district = fields.String(required=True)

    city_code = fields.String(required=True, validate=validate.Length(equal=7))
    city_name = fields.String(required=True)
    state = fields.String(required=True, validate=validate.Length(equal=2))
    zip_code = fields.String(required=True, validate=validate.Length(equal=8))

    country_code = fields.String(load_default="1058", dump_default="1058")
    country_name = fields.String(load_default="Brasil", dump_default="Brasil")

    phone = fields.String(allow_none=True)
    email = fields.Email(allow_none=True)
    is_default = fields.Boolean(load_default=True)

    @validates_schema
    def validate_fiscal_profile(self, data, **kwargs):
        cnpj = "".join(filter(str.isdigit, str(data.get("cnpj", ""))))
        zip_code = "".join(filter(str.isdigit, str(data.get("zip_code", ""))))
        city_code = "".join(filter(str.isdigit, str(data.get("city_code", ""))))

        errors = {}

        if len(cnpj) != 14:
            errors["cnpj"] = ["CNPJ deve conter 14 dígitos."]

        if len(zip_code) != 8:
            errors["zip_code"] = ["CEP deve conter 8 dígitos."]

        if len(city_code) != 7:
            errors["city_code"] = ["Código IBGE do município deve conter 7 dígitos."]

        if data.get("state"):
            data["state"] = data["state"].upper()

        if errors:
            raise ValidationError(errors)