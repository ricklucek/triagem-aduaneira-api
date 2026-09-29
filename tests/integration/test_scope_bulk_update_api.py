from datetime import datetime, timedelta
from uuid import UUID

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Client,
    Organization,
    Scope,
    ScopeAssignment,
    ScopeVersion,
    User,
    UserTag,
    UserTagAssignment,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "scope-bulk-update-test-secret"
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


def _tag(organization, code, name, color):
    tag = UserTag(
        organization_id=organization.id,
        code=code,
        name=name,
        color=color,
        is_master=False,
        is_system=True,
        active=True,
    )
    db.session.add(tag)
    return tag


def _draft(*, operations, commercial_id, da_import_id=None, da_export_id=None, keyword=""):
    operation = {"tipos": operations}
    if "IMPORTACAO" in operations:
        operation["importacao"] = {
            "analistaDA": [da_import_id] if da_import_id else [],
            "analistaAE": [],
            "produtosImportados": keyword,
        }
    if "EXPORTACAO" in operations:
        operation["exportacao"] = {
            "analistaDA": [da_export_id] if da_export_id else [],
            "analistaAE": [],
            "produtosExportados": keyword,
        }
    return {
        "sobreEmpresa": {"responsavelComercial": commercial_id},
        "operacao": operation,
    }


@pytest.fixture
def bulk_api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Bulk", slug="org-bulk")
        other_organization = Organization(nome="Outra Bulk", slug="outra-bulk")
        db.session.add_all([organization, other_organization])
        db.session.flush()

        admin = _user(organization, "Admin Bulk", "admin")
        commercial = _user(organization, "Comercial Atual", "comercial")
        commercial_target = _user(organization, "Comercial Novo", "comercial")
        da_current = _user(organization, "Analista DA Atual")
        da_target = _user(organization, "Analista DA Novo")
        ae_target = _user(organization, "Analista AE Novo")
        regular = _user(organization, "Usuário Comum")
        outsider = _user(other_organization, "Admin Externo", "admin")
        db.session.flush()

        commercial_tag = _tag(organization, "comercial", "Comercial", "emerald")
        da_tag = _tag(organization, "analista-da", "Analista DA", "blue")
        ae_tag = _tag(organization, "analista-ae", "Analista AE", "violet")
        outsider_tag = _tag(other_organization, "analista-da", "Analista DA", "blue")
        db.session.flush()
        db.session.add_all(
            [
                UserTagAssignment(user_id=commercial.id, tag_id=commercial_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=commercial_target.id, tag_id=commercial_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=da_current.id, tag_id=da_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=da_target.id, tag_id=da_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=ae_target.id, tag_id=ae_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=outsider.id, tag_id=outsider_tag.id, assigned_by_id=outsider.id),
            ]
        )

        import_client = Client(
            organization_id=organization.id,
            cnpj="00144009000176",
            razao_social="Madeiras Aurora Internacional",
            nome_resumido="Aurora",
        )
        export_client = Client(
            organization_id=organization.id,
            cnpj="32157202000138",
            razao_social="Exportadora Horizonte",
            nome_resumido="Horizonte",
        )
        outside_client = Client(
            organization_id=other_organization.id,
            cnpj="12345678000199",
            razao_social="Cliente Externo",
            nome_resumido="Externo",
        )
        db.session.add_all([import_client, export_client, outside_client])
        db.session.flush()

        import_draft = _draft(
            operations=["IMPORTACAO"],
            commercial_id=str(commercial.id),
            da_import_id=str(da_current.id),
            keyword="válvulas industriais madeira",
        )
        export_draft = _draft(
            operations=["EXPORTACAO"],
            commercial_id=str(commercial.id),
            da_export_id=str(da_current.id),
            keyword="papel celulose",
        )
        import_scope = Scope(
            organization_id=organization.id,
            client_id=import_client.id,
            status="published",
            version=2,
            draft=import_draft,
            published_snapshot=import_draft,
            created_by_id=admin.id,
            responsible_user_id=commercial.id,
        )
        export_scope = Scope(
            organization_id=organization.id,
            client_id=export_client.id,
            status="draft",
            version=1,
            draft=export_draft,
            created_by_id=admin.id,
            responsible_user_id=commercial.id,
        )
        outside_scope = Scope(
            organization_id=other_organization.id,
            client_id=outside_client.id,
            status="published",
            version=1,
            draft=_draft(
                operations=["IMPORTACAO"],
                commercial_id=str(outsider.id),
                da_import_id=str(outsider.id),
            ),
            created_by_id=outsider.id,
            responsible_user_id=outsider.id,
        )
        db.session.add_all([import_scope, export_scope, outside_scope])
        db.session.flush()
        db.session.add_all(
            [
                ScopeAssignment(scope_id=import_scope.id, user_id=commercial.id, role="RESPONSAVEL_COMERCIAL", active=True),
                ScopeAssignment(scope_id=import_scope.id, user_id=da_current.id, role="ANALISTA_DA_IMPORT", active=True),
                ScopeAssignment(scope_id=export_scope.id, user_id=commercial.id, role="RESPONSAVEL_COMERCIAL", active=True),
                ScopeAssignment(scope_id=export_scope.id, user_id=da_current.id, role="ANALISTA_DA_EXPORT", active=True),
                ScopeAssignment(scope_id=outside_scope.id, user_id=outsider.id, role="ANALISTA_DA_IMPORT", active=True),
            ]
        )
        db.session.commit()

        yield app.test_client(), {
            "app": app,
            "admin": _token(app, admin),
            "regular": _token(app, regular),
            "import_scope_id": str(import_scope.id),
            "export_scope_id": str(export_scope.id),
            "outside_scope_id": str(outside_scope.id),
            "da_tag_id": str(da_tag.id),
            "outsider_tag_id": str(outsider_tag.id),
            "da_target_id": str(da_target.id),
            "ae_target_id": str(ae_target.id),
            "commercial_target_id": str(commercial_target.id),
            "regular_id": str(regular.id),
        }
        db.session.remove()
        db.drop_all()


def test_bulk_endpoints_are_admin_only_and_expose_field_options(bulk_api):
    client, context = bulk_api

    forbidden = client.get("/scopes/bulk/options", headers=context["regular"])
    response = client.get("/scopes/bulk/options", headers=context["admin"])

    assert forbidden.status_code == 403
    assert response.status_code == 200
    assert [field["value"] for field in response.get_json()["fields"]] == [
        "responsavel_comercial",
        "analista_da_importacao",
        "analista_ae_importacao",
        "analista_da_exportacao",
        "analista_ae_exportacao",
    ]


def test_candidates_search_inside_scope_and_support_filters(bulk_api):
    client, context = bulk_api

    response = client.get(
        "/scopes/bulk/candidates",
        headers=context["admin"],
        query_string={
            "q": "Aurora madeira",
            "status": "published",
            "operation": "IMPORTACAO",
            "tagId": context["da_tag_id"],
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == context["import_scope_id"]
    assert body["items"][0]["assignments"]["analista_da_importacao"][0]["name"] == "Analista DA Atual"


def test_cross_organization_tag_and_scope_are_never_exposed(bulk_api):
    client, context = bulk_api

    tag_response = client.get(
        "/scopes/bulk/candidates",
        headers=context["admin"],
        query_string={"tagId": context["outsider_tag_id"]},
    )
    preview = client.post(
        "/scopes/bulk/preview",
        headers=context["admin"],
        json={
            "field": "analista_da_importacao",
            "targetUserId": context["da_target_id"],
            "scopeIds": [context["outside_scope_id"]],
        },
    )

    assert tag_response.status_code == 400
    assert preview.status_code == 200
    assert preview.get_json()["eligibleScopes"] == 0
    assert preview.get_json()["skipped"][0]["reason"] == "not_found_or_forbidden"


def test_preview_identifies_operation_mismatch_and_requires_matching_tag(bulk_api):
    client, context = bulk_api
    payload = {
        "field": "analista_da_importacao",
        "targetUserId": context["da_target_id"],
        "scopeIds": [context["import_scope_id"], context["export_scope_id"]],
    }

    response = client.post("/scopes/bulk/preview", headers=context["admin"], json=payload)
    invalid_user = client.post(
        "/scopes/bulk/preview",
        headers=context["admin"],
        json={**payload, "targetUserId": context["regular_id"]},
    )

    assert response.status_code == 200
    assert response.get_json()["eligibleScopes"] == 1
    assert response.get_json()["skipped"][0]["reason"] == "operation_not_enabled"
    assert invalid_user.status_code == 400
    assert "analista-da" in invalid_user.get_json()["message"]


def test_apply_updates_relational_assignment_draft_and_published_version(bulk_api):
    client, context = bulk_api

    response = client.post(
        "/scopes/bulk/apply",
        headers=context["admin"],
        json={
            "field": "analista_da_importacao",
            "targetUserId": context["da_target_id"],
            "scopeIds": [context["import_scope_id"]],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["impactedScopes"] == 1
    with context["app"].app_context():
        scope = db.session.get(Scope, UUID(context["import_scope_id"]))
        assert scope.draft["operacao"]["importacao"]["analistaDA"] == [context["da_target_id"]]
        assert scope.published_snapshot["operacao"]["importacao"]["analistaDA"] == [context["da_target_id"]]
        assert scope.version == 3
        active = ScopeAssignment.query.filter_by(
            scope_id=scope.id,
            role="ANALISTA_DA_IMPORT",
            active=True,
        ).all()
        assert [str(item.user_id) for item in active] == [context["da_target_id"]]
        version = ScopeVersion.query.filter_by(scope_id=scope.id, version_number=3).one()
        assert version.created_by_id is not None

    repeated = client.post(
        "/scopes/bulk/apply",
        headers=context["admin"],
        json={
            "field": "analista_da_importacao",
            "targetUserId": context["da_target_id"],
            "scopeIds": [context["import_scope_id"]],
        },
    )
    assert repeated.status_code == 200
    assert repeated.get_json()["impactedScopes"] == 0
    assert repeated.get_json()["skipped"][0]["reason"] == "already_assigned"


def test_export_field_updates_only_the_export_schema_branch(bulk_api):
    client, context = bulk_api

    response = client.post(
        "/scopes/bulk/apply",
        headers=context["admin"],
        json={
            "field": "analista_ae_exportacao",
            "targetUserId": context["ae_target_id"],
            "scopeIds": [context["export_scope_id"], context["import_scope_id"]],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["impactedScopes"] == 1
    assert response.get_json()["skipped"][0]["reason"] == "operation_not_enabled"
    with context["app"].app_context():
        export_scope = db.session.get(Scope, UUID(context["export_scope_id"]))
        import_scope = db.session.get(Scope, UUID(context["import_scope_id"]))
        assert export_scope.draft["operacao"]["exportacao"]["analistaAE"] == [context["ae_target_id"]]
        assert import_scope.draft["operacao"]["importacao"]["analistaAE"] == []


def test_commercial_update_syncs_scope_field_and_draft(bulk_api):
    client, context = bulk_api

    response = client.post(
        "/scopes/bulk/apply",
        headers=context["admin"],
        json={
            "field": "responsavel_comercial",
            "targetUserId": context["commercial_target_id"],
            "scopeIds": [context["export_scope_id"]],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["impactedScopes"] == 1
    with context["app"].app_context():
        scope = db.session.get(Scope, UUID(context["export_scope_id"]))
        assert str(scope.responsible_user_id) == context["commercial_target_id"]
        assert scope.draft["sobreEmpresa"]["responsavelComercial"] == context["commercial_target_id"]
