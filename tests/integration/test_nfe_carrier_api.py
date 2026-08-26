from datetime import datetime, timedelta

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Client,
    FiscalMunicipality,
    ImportProcess,
    NfeCarrier,
    NfeDraft,
    Organization,
    User,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "carrier-api-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Teste", slug="org-carriers")
        other_organization = Organization(nome="Outra Organização", slug="org-carriers-other")
        db.session.add_all([organization, other_organization])
        db.session.flush()
        user = User(
            organization_id=organization.id,
            nome="Administrador Teste",
            email="carrier-admin@example.invalid",
            role="admin",
            ativo=True,
        )
        user.set_password("test-password")
        importer = Client(
            organization_id=organization.id,
            cnpj="00000000000191",
            razao_social="Importadora Teste Ltda",
            ativo=True,
        )
        municipality = FiscalMunicipality(
            code="4106902",
            name="Curitiba",
            state="PR",
            active=True,
            updated_at=datetime.utcnow(),
        )
        hidden_carrier = NfeCarrier(
            organization_id=other_organization.id,
            legal_name="Transportadora de Outro Tenant",
            tax_id="11111111000191",
            street="Rua Externa",
            number="1",
            district="Centro",
            municipality_code="4106902",
            municipality_name="Curitiba",
            state="PR",
            zip_code="80000000",
            active=True,
        )
        db.session.add_all([user, importer, municipality, hidden_carrier])
        db.session.flush()
        process = ImportProcess(
            organization_id=organization.id,
            importer_id=importer.id,
            reference_code="CARRIER-TEST-001",
            status="created",
            source="manual",
            created_by_user_id=user.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(process)
        db.session.flush()
        draft = NfeDraft(
            organization_id=organization.id,
            import_process_id=process.id,
            importer_id=importer.id,
            model="55",
            purpose="normal",
            operation_type="entry",
            environment="production",
            series="1",
            status="draft",
            fiscal_payload={
                "document": {"environment": "production", "series": "1"},
                "transport": {"freight_mode": "9"},
                "items": [],
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(draft)
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
        yield (
            app.test_client(),
            {"Authorization": f"Bearer {token}"},
            str(draft.id),
        )
        db.session.remove()
        db.drop_all()


def carrier_payload(**overrides):
    payload = {
        "legal_name": "Transportadora Teste Ltda",
        "trade_name": "Trans Teste",
        "tax_id": "12.345.678/0001-90",
        "state_registration": "1234567890",
        "street": "Rua das Transportadoras",
        "number": "100",
        "complement": "Galpão 2",
        "district": "CIC",
        "municipality_code": "4106902",
        "zip_code": "81200000",
        "phone": "41999999999",
        "email": "fiscal@transportadora.test",
    }
    payload.update(overrides)
    return payload


def test_carrier_crud_normalizes_and_uses_official_municipality(api):
    client, headers, _ = api
    created = client.post("/nfe-carriers", headers=headers, json=carrier_payload())

    assert created.status_code == 201, created.get_json()
    body = created.get_json()
    assert body["tax_id"] == "12345678000190"
    assert body["municipality_code"] == "4106902"
    assert body["municipality_name"] == "Curitiba"
    assert body["state"] == "PR"
    assert body["active"] is True

    listed = client.get("/nfe-carriers?q=12345678&active=true", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["total"] == 1
    assert listed.get_json()["items"][0]["id"] == body["id"]

    updated = client.patch(
        f"/nfe-carriers/{body['id']}",
        headers=headers,
        json={"trade_name": "Transportadora Atualizada"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["trade_name"] == "Transportadora Atualizada"

    deactivated = client.delete(f"/nfe-carriers/{body['id']}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.get_json()["active"] is False


def test_carrier_list_is_scoped_to_current_organization(api):
    client, headers, _ = api
    response = client.get("/nfe-carriers", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_duplicate_tax_id_returns_existing_carrier(api):
    client, headers, _ = api
    first = client.post("/nfe-carriers", headers=headers, json=carrier_payload())
    duplicate = client.post(
        "/nfe-carriers",
        headers=headers,
        json=carrier_payload(legal_name="Outra Razão Social"),
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"] == "carrier_already_exists"
    assert duplicate.get_json()["carrier_id"] == first.get_json()["id"]


def test_registered_carrier_is_copied_to_draft_snapshot(api):
    client, headers, draft_id = api
    created = client.post("/nfe-carriers", headers=headers, json=carrier_payload())
    carrier_id = created.get_json()["id"]

    updated_draft = client.patch(
        f"/nfe-drafts/{draft_id}",
        headers=headers,
        json={
            "transport": {
                "freight_mode": "0",
                "carrier_id": carrier_id,
            }
        },
    )
    assert updated_draft.status_code == 200, updated_draft.get_json()
    snapshot = updated_draft.get_json()["draft"]["fiscal_payload"]["transport"]["carrier"]
    assert snapshot["source_carrier_id"] == carrier_id
    assert snapshot["name"] == "Transportadora Teste Ltda"
    assert snapshot["city_name"] == "Curitiba"
    assert snapshot["address"] == "Rua das Transportadoras, 100, Galpão 2, CIC"

    changed = client.patch(
        f"/nfe-carriers/{carrier_id}",
        headers=headers,
        json={"legal_name": "Nome Alterado no Cadastro"},
    )
    assert changed.status_code == 200

    draft_after_change = client.get(f"/nfe-drafts/{draft_id}", headers=headers)
    preserved = draft_after_change.get_json()["draft"]["fiscal_payload"]["transport"]["carrier"]
    assert preserved["name"] == "Transportadora Teste Ltda"


def test_registered_carrier_cannot_be_combined_with_manual_data(api):
    client, headers, draft_id = api
    created = client.post("/nfe-carriers", headers=headers, json=carrier_payload())

    response = client.patch(
        f"/nfe-drafts/{draft_id}",
        headers=headers,
        json={
            "transport": {
                "carrier_id": created.get_json()["id"],
                "carrier": {"name": "Manual"},
            }
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "validation_error"


def test_manual_carrier_replaces_registered_snapshot(api):
    client, headers, draft_id = api
    created = client.post("/nfe-carriers", headers=headers, json=carrier_payload())
    selected = client.patch(
        f"/nfe-drafts/{draft_id}",
        headers=headers,
        json={"transport": {"carrier_id": created.get_json()["id"]}},
    )
    assert selected.status_code == 200

    manual = client.patch(
        f"/nfe-drafts/{draft_id}",
        headers=headers,
        json={
            "transport": {
                "carrier": {
                    "name": "Transportadora preenchida manualmente",
                    "tax_id": "12345678901",
                    "city_name": "Curitiba",
                    "state": "PR",
                }
            }
        },
    )
    assert manual.status_code == 200
    snapshot = manual.get_json()["draft"]["fiscal_payload"]["transport"]["carrier"]
    assert snapshot == {
        "name": "Transportadora preenchida manualmente",
        "tax_id": "12345678901",
        "city_name": "Curitiba",
        "state": "PR",
    }
