from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from .models import (
    Admin,
    Scope,
    User,
    Preposto,
    PrepostoContato,
    PrepostoLocalidade,
)


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


class PrepostoContatoSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrepostoContato
        load_instance = True
        include_fk = True
        exclude = ("created_at",)


class PrepostoLocalidadeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrepostoLocalidade
        load_instance = True
        include_fk = True
        exclude = ("created_at",)


class PrepostoSchema(SQLAlchemyAutoSchema):
    contatos = fields.Nested(PrepostoContatoSchema, many=True, dump_only=True)
    localidades = fields.Nested(PrepostoLocalidadeSchema, many=True, dump_only=True)

    class Meta:
        model = Preposto
        load_instance = True
        exclude = ("created_at",)


class PrepostoLookupItemSchema(Schema):
    id = fields.String(required=True)
    nome = fields.String(required=True)
    cidade = fields.String(required=True)
    uf = fields.String(allow_none=True)
    descricaoLocal = fields.String(allow_none=True)
    operacao = fields.String(required=True)
    valor = fields.Decimal(as_string=False, allow_none=True)
    valorDescricao = fields.String(allow_none=True)
    moeda = fields.String(required=True)
    telefone = fields.String(allow_none=True)
    email = fields.String(allow_none=True)
    contatoNome = fields.String(allow_none=True)
    observacoes = fields.String(allow_none=True)


class PrepostoLookupResponseSchema(Schema):
    items = fields.List(fields.Nested(PrepostoLookupItemSchema), required=True)
    total = fields.Integer(required=True)


class PrepostoCreateSchema(Schema):
    nome = fields.String(required=True)
    razao_social = fields.String(allow_none=True)
    ativo = fields.Boolean(load_default=True)
    observacoes = fields.String(allow_none=True)


class PrepostoUpdateSchema(Schema):
    nome = fields.String(required=False)
    razao_social = fields.String(allow_none=True, required=False)
    ativo = fields.Boolean(required=False)
    observacoes = fields.String(allow_none=True, required=False)


class PrepostoContatoCreateSchema(Schema):
    nome = fields.String(required=True)
    email = fields.Email(allow_none=True)
    telefone = fields.String(allow_none=True)
    whatsapp = fields.String(allow_none=True)
    principal = fields.Boolean(load_default=False)


class PrepostoContatoUpdateSchema(Schema):
    nome = fields.String(required=False)
    email = fields.Email(allow_none=True, required=False)
    telefone = fields.String(allow_none=True, required=False)
    whatsapp = fields.String(allow_none=True, required=False)
    principal = fields.Boolean(required=False)


class PrepostoLocalidadeCreateSchema(Schema):
    cidade = fields.String(required=True)
    uf = fields.String(allow_none=True)
    descricao_local = fields.String(allow_none=True)
    tipo_local = fields.String(
        allow_none=True,
        validate=validate.OneOf(["CIDADE", "PORTO", "AEROPORTO", "CLIA", "FRONTEIRA"]),
    )
    atende_importacao = fields.Boolean(load_default=False)
    atende_exportacao = fields.Boolean(load_default=False)
    valor_importacao = fields.Decimal(as_string=False, allow_none=True)
    valor_exportacao = fields.Decimal(as_string=False, allow_none=True)
    valor_importacao_descricao = fields.String(allow_none=True)
    valor_exportacao_descricao = fields.String(allow_none=True)
    moeda = fields.String(load_default="BRL")
    observacoes = fields.String(allow_none=True)

    @validates_schema
    def validate_operacao(self, data, **kwargs):
        if not data.get("atende_importacao") and not data.get("atende_exportacao"):
            raise ValidationError(
                "A localidade deve atender importação e/ou exportação.",
                field_name="atende_importacao",
            )


class PrepostoLocalidadeUpdateSchema(Schema):
    cidade = fields.String(required=False)
    uf = fields.String(allow_none=True, required=False)
    descricao_local = fields.String(allow_none=True, required=False)
    tipo_local = fields.String(
        allow_none=True,
        required=False,
        validate=validate.OneOf(["CIDADE", "PORTO", "AEROPORTO", "CLIA", "FRONTEIRA"]),
    )
    atende_importacao = fields.Boolean(required=False)
    atende_exportacao = fields.Boolean(required=False)
    valor_importacao = fields.Decimal(as_string=False, allow_none=True, required=False)
    valor_exportacao = fields.Decimal(as_string=False, allow_none=True, required=False)
    valor_importacao_descricao = fields.String(allow_none=True, required=False)
    valor_exportacao_descricao = fields.String(allow_none=True, required=False)
    moeda = fields.String(required=False)
    observacoes = fields.String(allow_none=True, required=False)