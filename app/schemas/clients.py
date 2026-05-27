from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from app.models import Client, ClientContact
from .common import UUIDStringField


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


class ClientContactSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    clientId = UUIDStringField(attribute="client_id", dump_only=True)
    departmentRole = fields.String(attribute="department_role", allow_none=True)

    class Meta:
        model = ClientContact
        load_instance = True
        include_fk = True
        exclude = ("client_id", "department_role")


class ClientSchema(SQLAlchemyAutoSchema):
    id = UUIDStringField(dump_only=True)
    organizationId = UUIDStringField(attribute="organization_id", dump_only=True)
    taxId = fields.String(attribute="tax_id", required=True)
    legalName = fields.String(attribute="legal_name", required=True)
    tradeName = fields.String(attribute="trade_name", allow_none=True)
    stateRegistration = fields.String(attribute="state_registration", allow_none=True)
    municipalRegistration = fields.String(attribute="municipal_registration", allow_none=True)
    officeAddress = fields.String(attribute="office_address", allow_none=True)
    warehouseAddress = fields.String(attribute="warehouse_address", allow_none=True)
    mainCnae = fields.String(attribute="main_cnae", allow_none=True)
    secondaryCnae = fields.String(attribute="secondary_cnae", allow_none=True)
    taxRegime = fields.String(attribute="tax_regime", allow_none=True)
    radarMode = fields.String(attribute="radar_mode", allow_none=True)
    contacts = fields.Nested(ClientContactSchema, many=True, dump_only=True)

    class Meta:
        model = Client
        load_instance = True
        include_fk = True
        exclude = (
            "organization_id",
            "tax_id",
            "legal_name",
            "trade_name",
            "state_registration",
            "municipal_registration",
            "office_address",
            "warehouse_address",
            "main_cnae",
            "secondary_cnae",
            "tax_regime",
            "radar_mode",
        )


class ClientSummarySchema(Schema):
    id = UUIDStringField()
    taxId = fields.String(attribute="tax_id", allow_none=True)
    legalName = fields.String(attribute="legal_name", allow_none=True)
    tradeName = fields.String(attribute="trade_name", allow_none=True)


class ClientContactPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    name = fields.String(required=True)
    departmentRole = fields.String(attribute="department_role", allow_none=True, load_default=None)
    email = fields.Email(allow_none=True, load_default=None)
    phone = fields.String(allow_none=True, load_default=None)
    whatsapp = fields.String(allow_none=True, load_default=None)
    primary = fields.Boolean(load_default=False)
    active = fields.Boolean(load_default=True)


class ClientPayloadSchema(Schema):
    id = UUIDStringField(required=False, allow_none=True)
    taxId = fields.String(attribute="tax_id", required=True, validate=validate.Length(min=11, max=14))
    legalName = fields.String(attribute="legal_name", required=True)
    tradeName = fields.String(attribute="trade_name", allow_none=True, load_default=None)
    stateRegistration = fields.String(attribute="state_registration", allow_none=True, load_default=None)
    municipalRegistration = fields.String(attribute="municipal_registration", allow_none=True, load_default=None)
    officeAddress = fields.String(attribute="office_address", allow_none=True, load_default=None)
    warehouseAddress = fields.String(attribute="warehouse_address", allow_none=True, load_default=None)
    mainCnae = fields.String(attribute="main_cnae", allow_none=True, load_default=None)
    secondaryCnae = fields.String(attribute="secondary_cnae", allow_none=True, load_default=None)
    taxRegime = fields.String(attribute="tax_regime", allow_none=True, load_default=None)
    radarMode = fields.String(attribute="radar_mode", allow_none=True, load_default=None)
