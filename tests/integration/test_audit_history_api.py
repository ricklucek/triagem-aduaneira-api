from copy import deepcopy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    AuditEvent,
    AuditEventChange,
    Client,
    Organization,
    Scope,
    ScopeAssignment,
    ScopeVersion,
    User,
    UserTag,
    UserTagAssignment,
)
from app.services.audit_service import sanitize_audit_value


class TestConfig:
    TESTING = True
    SECRET_KEY = "audit-history-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_EXPIRES_SECONDS = 3600
    JWT_REFRESH_EXPIRES_SECONDS = 604800


def _token(app, user):
    now = datetime.utcnow()
    encoded = jwt.encode(
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
    return {"Authorization": f"Bearer {encoded}"}


def _user(organization, name, role="operacao"):
    user = User(
        organization_id=organization.id,
        nome=name,
        email=f"{name.lower().replace(' ', '-')}@example.invalid",
        role=role,
        setor="Operações",
        ativo=True,
    )
    user.set_password("test-password")
    db.session.add(user)
    return user


def _draft(client, commercial_id, *, note="original"):
    return {
        "sobreEmpresa": {
            "cnpj": client.cnpj,
            "razaoSocial": client.razao_social,
            "nomeResumido": client.nome_resumido,
            "responsavelComercial": str(commercial_id),
        },
        "operacao": {"tipos": ["IMPORTACAO"], "importacao": {"observacoes": note}},
    }


@pytest.fixture
def audit_api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Audit", slug="org-audit")
        other = Organization(nome="Outra Audit", slug="outra-audit")
        db.session.add_all([organization, other])
        db.session.flush()

        admin = _user(organization, "Admin Audit", "admin")
        regular = _user(organization, "Pessoa Audit")
        commercial = _user(organization, "Comercial Audit", "comercial")
        commercial_target = _user(organization, "Comercial Novo", "comercial")
        outsider = _user(other, "Admin Outra", "admin")
        db.session.flush()

        commercial_tag = UserTag(
            organization_id=organization.id,
            code="comercial",
            name="Comercial",
            color="emerald",
            is_system=True,
            active=True,
        )
        db.session.add(commercial_tag)
        db.session.flush()
        db.session.add_all(
            [
                UserTagAssignment(user_id=commercial.id, tag_id=commercial_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=commercial_target.id, tag_id=commercial_tag.id, assigned_by_id=admin.id),
            ]
        )

        clients = [
            Client(
                organization_id=organization.id,
                cnpj="00144009000176",
                razao_social="Cliente Histórico Um",
                nome_resumido="Histórico Um",
            ),
            Client(
                organization_id=organization.id,
                cnpj="32157202000138",
                razao_social="Cliente Histórico Dois",
                nome_resumido="Histórico Dois",
            ),
        ]
        db.session.add_all(clients)
        db.session.flush()
        scopes = []
        for client in clients:
            draft = _draft(client, commercial.id)
            scope = Scope(
                organization_id=organization.id,
                client_id=client.id,
                status="published",
                version=1,
                draft=deepcopy(draft),
                published_snapshot=deepcopy(draft),
                created_by_id=admin.id,
                responsible_user_id=commercial.id,
            )
            db.session.add(scope)
            db.session.flush()
            db.session.add(
                ScopeAssignment(
                    scope_id=scope.id,
                    user_id=commercial.id,
                    role="RESPONSAVEL_COMERCIAL",
                    active=True,
                )
            )
            scopes.append(scope)

        private_scope = Scope(
            organization_id=organization.id,
            status="draft",
            version=1,
            draft={"sobreEmpresa": {"razaoSocial": "Rascunho privado"}},
            created_by_id=admin.id,
        )
        db.session.add(private_scope)
        db.session.commit()

        yield app.test_client(), {
            "app": app,
            "admin": _token(app, admin),
            "regular": _token(app, regular),
            "outsider": _token(app, outsider),
            "admin_id": str(admin.id),
            "regular_id": str(regular.id),
            "commercial_target_id": str(commercial_target.id),
            "scope_ids": [str(scope.id) for scope in scopes],
            "private_scope_id": str(private_scope.id),
        }
        db.session.remove()
        db.drop_all()


def test_scope_and_user_events_are_filtered_and_do_not_expose_passwords(audit_api):
    client, context = audit_api
    scope_id = context["scope_ids"][0]
    detail = client.get(f"/scopes/{scope_id}", headers=context["admin"]).get_json()
    draft = detail["draft"]
    draft["operacao"]["importacao"]["observacoes"] = "ajustado"

    assert client.put(f"/scopes/{scope_id}", headers=context["admin"], json=draft).status_code == 200
    assert client.put(
        f"/users/user/{context['regular_id']}",
        headers=context["admin"],
        json={"setor": "Financeiro", "password": "nova-senha-segura"},
    ).status_code == 200

    admin_events = client.get("/audit/events", headers=context["admin"]).get_json()
    actions = {item["action"] for item in admin_events["items"]}
    assert "scope.updated" in actions
    assert "user.updated" in actions

    user_event = next(item for item in admin_events["items"] if item["action"] == "user.updated")
    user_detail = client.get(f"/audit/events/{user_event['id']}", headers=context["admin"]).get_json()
    serialized = str(user_detail).lower()
    assert "password_hash" not in serialized
    assert "nova-senha-segura" not in serialized
    assert user_detail["changes"][0]["after"]["credentialsChanged"] is True

    regular_events = client.get("/audit/events", headers=context["regular"]).get_json()
    assert {item["module"] for item in regular_events["items"]} == {"scopes"}
    assert any(item["action"] == "scope.updated" for item in regular_events["items"])

    outsider_events = client.get("/audit/events", headers=context["outsider"]).get_json()
    assert outsider_events["total"] == 0


def test_bulk_batches_share_one_event_and_admin_can_reverse_them(audit_api):
    client, context = audit_api
    operation_id = str(uuid4())
    for scope_id in context["scope_ids"]:
        response = client.post(
            "/scopes/bulk/apply",
            headers=context["admin"],
            json={
                "field": "responsavel_comercial",
                "targetUserId": context["commercial_target_id"],
                "scopeIds": [scope_id],
                "operationId": operation_id,
            },
        )
        assert response.status_code == 200
        assert response.get_json()["operationId"] == operation_id

    events = client.get(
        "/audit/events",
        headers=context["admin"],
        query_string={"action": "scope.bulk_updated"},
    ).get_json()
    assert events["total"] == 1
    event = events["items"][0]
    assert event["operationId"] == operation_id
    assert event["affectedCount"] == 2

    preview = client.post(
        f"/audit/events/{event['id']}/reversal-preview",
        headers=context["admin"],
    )
    assert preview.status_code == 200
    assert preview.get_json()["eligible"] == 2
    assert client.post(
        f"/audit/events/{event['id']}/reverse",
        headers=context["regular"],
        json={"confirmation": "REVERTER"},
    ).status_code == 403

    reversed_response = client.post(
        f"/audit/events/{event['id']}/reverse",
        headers=context["admin"],
        json={"confirmation": "REVERTER"},
    )
    assert reversed_response.status_code == 200
    assert reversed_response.get_json()["result"] == {
        "reverted": 2,
        "skipped": 0,
        "conflicts": 0,
    }

    with context["app"].app_context():
        for scope_id in context["scope_ids"]:
            scope = db.session.get(Scope, UUID(scope_id))
            assert scope.version == 3
            assert ScopeVersion.query.filter_by(scope_id=scope.id, version_number=3).one()
        source = db.session.get(AuditEvent, UUID(event["id"]))
        reversal = AuditEvent.query.filter_by(reverses_event_id=source.id).one()
        assert AuditEventChange.query.filter_by(event_id=reversal.id).count() == 2


def test_reversal_detects_a_later_change_and_preserves_current_state(audit_api):
    client, context = audit_api
    scope_id = context["scope_ids"][0]
    first = client.get(f"/scopes/{scope_id}", headers=context["admin"]).get_json()["draft"]
    first["operacao"]["importacao"]["observacoes"] = "primeira alteração"
    assert client.put(f"/scopes/{scope_id}", headers=context["admin"], json=first).status_code == 200
    first_event = client.get(
        "/audit/events",
        headers=context["admin"],
        query_string={"action": "scope.updated"},
    ).get_json()["items"][0]

    second = deepcopy(first)
    second["operacao"]["importacao"]["observacoes"] = "alteração posterior"
    assert client.put(f"/scopes/{scope_id}", headers=context["admin"], json=second).status_code == 200

    preview = client.post(
        f"/audit/events/{first_event['id']}/reversal-preview",
        headers=context["admin"],
    ).get_json()
    assert preview["eligible"] == 0
    assert preview["conflicts"] == 1
    response = client.post(
        f"/audit/events/{first_event['id']}/reverse",
        headers=context["admin"],
        json={"confirmation": "REVERTER"},
    )
    assert response.status_code == 409

    current = client.get(f"/scopes/{scope_id}", headers=context["admin"]).get_json()
    assert current["draft"]["operacao"]["importacao"]["observacoes"] == "alteração posterior"


def test_sanitizer_recursively_removes_credentials_and_certificate_material():
    sanitized = sanitize_audit_value(
        {
            "name": "Registro seguro",
            "password": "segredo",
            "nested": {
                "senhaCertificado": "segredo-2",
                "accessToken": "token",
                "certificate_data": "pfx-binário",
                "allowed": "visível",
            },
        }
    )

    assert sanitized == {"name": "Registro seguro", "nested": {"allowed": "visível"}}


def test_scope_creation_and_deletion_remain_auditable_after_hard_delete(audit_api):
    client, context = audit_api
    created = client.post(
        "/scopes",
        headers=context["admin"],
        json={"sobreEmpresa": {"razaoSocial": "Rascunho removível"}},
    )
    assert created.status_code == 201
    scope_id = created.get_json()["id"]

    deleted = client.delete(f"/scopes/{scope_id}", headers=context["admin"])
    assert deleted.status_code == 204

    events = client.get("/audit/events", headers=context["admin"]).get_json()["items"]
    created_event = next(
        item for item in events
        if item["action"] == "scope.created" and item["entityId"] == scope_id
    )
    deleted_event = next(
        item for item in events
        if item["action"] == "scope.deleted" and item["entityId"] == scope_id
    )
    assert created_event["affectedCount"] == 1
    assert deleted_event["affectedCount"] == 1

    detail = client.get(
        f"/audit/events/{deleted_event['id']}", headers=context["admin"]
    ).get_json()
    assert detail["changes"][0]["before"]["id"] == scope_id
    assert detail["changes"][0]["after"] is None
