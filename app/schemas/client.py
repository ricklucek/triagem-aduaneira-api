from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import (
    Client,
    ClientContact,
)


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