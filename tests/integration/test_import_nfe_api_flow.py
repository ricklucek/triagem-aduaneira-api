from datetime import datetime, timedelta

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import Client, Organization, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "integration-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_EXPIRES_SECONDS = 3600
    JWT_REFRESH_EXPIRES_SECONDS = 604800


@pytest.fixture
def api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Teste", slug="org-teste")
        db.session.add(organization)
        db.session.flush()
        user = User(
            organization_id=organization.id,
            nome="Operador Teste",
            email="operador@example.invalid",
            role="admin",
            ativo=True,
        )
        user.set_password("test-password")
        client = Client(
            organization_id=organization.id,
            cnpj="00000000000191",
            razao_social="Importadora Teste Ltda",
            ativo=True,
        )
        db.session.add_all([user, client])
        db.session.commit()

        now = datetime.utcnow()
        token = jwt.encode(
            {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role,
                "principal_type": "user",
                "type": "access",
                "iat": now,
                "exp": now + timedelta(hours=1),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        yield app.test_client(), {"Authorization": f"Bearer {token}"}, str(client.id)
        db.session.remove()
        db.drop_all()


def test_api_flow_from_manual_duimp_snapshot_to_unsigned_xml(api):
    client, headers, importer_id = api

    profile = client.put(
        f"/clients/{importer_id}/fiscal-profile",
        headers=headers,
        json={
            "legal_name": "Importadora Teste Ltda",
            "cnpj": "00000000000191",
            "state_registration": "1234567890",
            "tax_regime": "3",
            "street": "Rua de Teste",
            "number": "100",
            "district": "Centro",
            "city_code": "4106902",
            "city_name": "Curitiba",
            "state": "PR",
            "zip_code": "80000000",
            "country_code": "1058",
            "country_name": "Brasil",
        },
    )
    assert profile.status_code == 200

    process_response = client.post(
        "/import-processes",
        headers=headers,
        json={
            "importer_id": importer_id,
            "reference_code": "TESTE-DUIMP-001",
            "duimp_number": "26BR0000000000-1",
            "source": "manual",
        },
    )
    assert process_response.status_code == 201
    process_id = process_response.get_json()["id"]

    draft_response = client.post(
        f"/import-processes/{process_id}/nfe-draft/from-duimp",
        headers=headers,
        json={
            "environment": "homologation",
            "series": "1",
            "number": 14422,
            "import_purpose": "resale",
            "duimp_payload": {
                "numero": "26BR0000000000-1",
                "versao": "1",
                "dataRegistro": "2026-07-14",
                "localDesembaraco": "0917800 - PORTO DE PARANAGUA",
                "ufDesembaraco": "PR",
                "dataDesembaraco": "2026-07-15",
                "viaTransporteCodigo": "1",
                "tipoIntermedio": "1",
                "modalidadeImportacao": "direct",
                "itens": [
                    {
                        "numeroItem": "1",
                        "codigoProduto": "PROD-001",
                        "descricao": "Produto sanitizado para teste",
                        "ncm": "87087090",
                        "quantidade": "12",
                        "unidade": "PECAS",
                        "valorProduto": "6054.39",
                        "valorUnitario": "504.5325",
                        "sequenciaAdicao": "1",
                        "codigoFabricante": "0000",
                        "codigoExportador": "EXP-TESTE-001",
                        "tributos": {
                            "ii": {"base": "6054.39", "rate": "18", "value": "1089.79"},
                            "ipi": {"base": "7144.18", "rate": "3.25", "value": "232.19"},
                            "pis": {"base": "6054.39", "rate": "3.12", "value": "188.90"},
                            "cofins": {"base": "6054.39", "rate": "14.37", "value": "870.02"},
                        },
                    }
                ],
            },
            "foreign_supplier": {
                "name": "Foreign Supplier Ltd",
                "foreign_id": "",
                "country_code": "1600",
                "country_name": "CHINA",
                "address": {
                    "street": "EXTERIOR",
                    "number": "0",
                    "district": "EXTERIOR",
                    "city_name": "EXTERIOR",
                },
            },
            "tax_configuration": {
                "icms_rate": "12",
                "icms_origin": "1",
                "icms_cst": "90",
                "ipi_cst": "49",
                "pis_cst": "98",
                "cofins_cst": "98",
            },
            "additional_costs": {"afrmm": "53.46", "other": "35.36"},
        },
    )
    assert draft_response.status_code == 201, draft_response.get_json()
    draft_body = draft_response.get_json()
    assert draft_body["validation"]["valid"] is True
    draft_id = draft_body["draft"]["id"]

    key_response = client.post(
        f"/nfe-drafts/{draft_id}/generate-access-key",
        headers=headers,
        json={},
    )
    assert key_response.status_code == 200, key_response.get_json()
    assert len(key_response.get_json()["access_key"]) == 44

    xml_response = client.post(
        f"/nfe-drafts/{draft_id}/generate-xml",
        headers=headers,
        json={},
    )
    assert xml_response.status_code == 201, xml_response.get_json()
    xml = xml_response.get_json()["xml_content"]
    assert "<nDI>26BR00000000001</nDI>" in xml
    assert "<UF>EX</UF>" in xml
    assert "<Signature" not in xml
