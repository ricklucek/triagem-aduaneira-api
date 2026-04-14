from marshmallow import Schema, ValidationError, fields, validate, validates_schema
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from .models import (
    Client,
    ClientContact,
    Organization,
    OrganizationSetting,
    Preposto,
    PrepostoContato,
    PrepostoLocalidade,
    Scope,
    ScopeAssignment,
    ScopeService,
    ScopeVersion,
    User,
)


class OrganizationSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Organization
        load_instance = True
        exclude = ("created_at", "updated_at")


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ("password_hash",)


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
    completeness_score = fields.Integer(required=True)
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


class OrganizationFixedInfoSchema(Schema):
    salarioMinimoVigente = fields.Decimal(as_string=False, required=True)
    dadosBancariosCasco = fields.Dict(required=True)

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


class OrganizationSettingSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = OrganizationSetting
        load_instance = True
        include_fk = True


class AdminSettingsSchema(Schema):
    salarioMinimoVigente = fields.Decimal(as_string=False, required=True)
    dadosBancariosCasco = fields.Dict(required=True)


class PrepostoContatoSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrepostoContato
        load_instance = True
        include_fk = True
        exclude = ("created_at", "updated_at")


class PrepostoLocalidadeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = PrepostoLocalidade
        load_instance = True
        include_fk = True
        exclude = ("created_at", "updated_at")


class PrepostoSchema(SQLAlchemyAutoSchema):
    contatos = fields.Nested(PrepostoContatoSchema, many=True, dump_only=True)
    localidades = fields.Nested(PrepostoLocalidadeSchema, many=True, dump_only=True)

    class Meta:
        model = Preposto
        load_instance = True
        exclude = ("created_at", "updated_at")


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
