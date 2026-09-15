from datetime import datetime, timedelta
from io import BytesIO

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import Client, ClientFiscalProfile, Organization, User
from app.services.fiscal_certificate import StoredCertificateReferences
from tests.helpers import certificate_material


class TestConfig:
    TESTING = True
    SECRET_KEY = "certificate-upload-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class MemoryWritableCertificateVault:
    def __init__(self):
        self.materials = {}
        self.store_calls = 0

    def store(
        self,
        *,
        organization_id,
        client_id,
        certificate_id,
        material,
    ):
        self.store_calls += 1
        certificate_ref = f"gcp:test-{certificate_id}-pfx@1"
        password_ref = f"gcp:test-{certificate_id}-password@1"
        self.materials[(certificate_ref, password_ref)] = material
        return StoredCertificateReferences(
            certificate_ref=certificate_ref,
            password_ref=password_ref,
        )

    def resolve(self, *, provider, certificate_ref, password_ref):
        del provider
        return self.materials[(certificate_ref, password_ref)]


def _token(app, user):
    now = datetime.utcnow()
    return jwt.encode(
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


@pytest.fixture
def api():
    app = create_app(TestConfig)
    vault = MemoryWritableCertificateVault()
    app.config["NFE_CERTIFICATE_VAULT"] = vault
    with app.app_context():
        db.create_all()
        organization = Organization(
            nome="Organização Certificados",
            slug="org-certificados",
        )
        db.session.add(organization)
        db.session.flush()
        admin = User(
            organization_id=organization.id,
            nome="Administrador Fiscal",
            email="admin-cert@example.invalid",
            role="admin",
            ativo=True,
        )
        operator = User(
            organization_id=organization.id,
            nome="Operador Fiscal",
            email="operator-cert@example.invalid",
            role="operacao",
            ativo=True,
        )
        admin.set_password("test-password")
        operator.set_password("test-password")
        client = Client(
            organization_id=organization.id,
            cnpj="00000000000191",
            razao_social="Importadora Certificado Ltda",
            ativo=True,
        )
        db.session.add_all([admin, operator, client])
        db.session.flush()
        db.session.add(
            ClientFiscalProfile(
                organization_id=organization.id,
                client_id=client.id,
                legal_name=client.razao_social,
                cnpj=client.cnpj,
                state_registration="1234567890",
                tax_regime="3",
                street="Rua de Teste",
                number="100",
                district="Centro",
                city_code="4106902",
                city_name="Curitiba",
                state="PR",
                zip_code="80000000",
                country_code="1058",
                country_name="Brasil",
                is_default=True,
            )
        )
        db.session.commit()
        yield {
            "client": app.test_client(),
            "client_id": str(client.id),
            "admin_headers": {
                "Authorization": f"Bearer {_token(app, admin)}"
            },
            "operator_headers": {
                "Authorization": f"Bearer {_token(app, operator)}"
            },
            "vault": vault,
        }
        db.session.remove()
        db.drop_all()


def _upload(api, material, *, headers=None, activate="true"):
    return api["client"].post(
        f"/clients/{api['client_id']}/fiscal-certificates/upload",
        headers=headers or api["admin_headers"],
        data={
            "certificate": (
                BytesIO(material.pkcs12_bytes),
                "cliente.pfx",
            ),
            "password": material.password.decode("utf-8"),
            "environment": "production",
            "activate": activate,
        },
        content_type="multipart/form-data",
    )


def test_admin_uploads_valid_a1_without_exposing_secret_references(api):
    material = certificate_material("00000000000191")

    response = _upload(api, material)

    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body["status"] == "active"
    assert body["is_active"] is True
    assert body["issuer_cnpj"] == "00000000000191"
    assert body["certificate_fingerprint_sha256"]
    assert body["certificate_serial_number"]
    assert body["created_by_name"] == "Administrador Fiscal"
    assert "certificate_ref" not in body
    assert "password_ref" not in body
    assert api["vault"].store_calls == 1


def test_upload_rejects_a1_from_another_cnpj_before_secret_storage(api):
    material = certificate_material("11111111000191")

    response = _upload(api, material)

    assert response.status_code == 422
    assert "não corresponde" in response.get_json()["message"]
    assert api["vault"].store_calls == 0


def test_new_active_certificate_rotates_previous_and_can_be_deactivated(api):
    first = _upload(api, certificate_material("00000000000191"))
    second = _upload(api, certificate_material("00000000000191"))

    assert first.status_code == 201
    assert second.status_code == 201
    listed = api["client"].get(
        f"/clients/{api['client_id']}/fiscal-certificates",
        headers=api["admin_headers"],
    )
    rows = listed.get_json()
    assert len(rows) == 2
    assert sum(row["is_active"] for row in rows) == 1
    previous = next(
        row for row in rows if row["id"] == first.get_json()["id"]
    )
    assert previous["status"] == "disabled"

    current_id = second.get_json()["id"]
    deactivated = api["client"].post(
        f"/clients/{api['client_id']}/fiscal-certificates/"
        f"{current_id}/deactivate",
        headers=api["admin_headers"],
    )
    assert deactivated.status_code == 200
    assert deactivated.get_json()["status"] == "disabled"
    assert deactivated.get_json()["is_active"] is False


def test_non_admin_cannot_upload_certificate(api):
    response = _upload(
        api,
        certificate_material("00000000000191"),
        headers=api["operator_headers"],
    )

    assert response.status_code == 403
    assert api["vault"].store_calls == 0
