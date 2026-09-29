from datetime import datetime, timedelta

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Client,
    Organization,
    Scope,
    ScopeAssignment,
    User,
    UserTag,
    UserTagAssignment,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "dashboard-tags-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_EXPIRES_SECONDS = 3600
    JWT_REFRESH_EXPIRES_SECONDS = 604800


def _token(app, user: User) -> dict:
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


def _client(organization, suffix, name):
    client = Client(
        organization_id=organization.id,
        cnpj=f"12345678000{suffix}",
        razao_social=name,
        nome_resumido=name,
    )
    db.session.add(client)
    return client


@pytest.fixture
def dashboard_api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Dashboard", slug="org-dashboard")
        other_organization = Organization(nome="Outra Organização", slug="outra-dashboard")
        db.session.add_all([organization, other_organization])
        db.session.flush()

        admin = _user(organization, "Admin Dashboard", "admin")
        commercial = _user(organization, "Comercial Dashboard", "comercial")
        analyst_da = _user(organization, "Analista DA")
        analyst_ae = _user(organization, "Analista AE")
        outsider = _user(other_organization, "Admin Externo Dashboard", "admin")
        db.session.flush()

        da_tag = _tag(organization, "analista-da", "Analista DA", "blue")
        ae_tag = _tag(organization, "analista-ae", "Analista AE", "violet")
        outsider_tag = _tag(other_organization, "analista-da", "Analista DA", "blue")
        db.session.flush()

        db.session.add_all(
            [
                UserTagAssignment(user_id=analyst_da.id, tag_id=da_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=analyst_ae.id, tag_id=ae_tag.id, assigned_by_id=admin.id),
                UserTagAssignment(user_id=outsider.id, tag_id=outsider_tag.id, assigned_by_id=outsider.id),
            ]
        )

        clients = [
            _client(organization, "01", "Cliente DA"),
            _client(organization, "02", "Cliente AE"),
            _client(organization, "03", "Cliente Rascunho Alheio"),
            _client(organization, "04", "Cliente Rascunho Próprio"),
            _client(other_organization, "05", "Cliente Externo"),
        ]
        db.session.flush()

        published_da = Scope(
            organization_id=organization.id,
            client_id=clients[0].id,
            status="published",
            draft={},
            created_by_id=commercial.id,
        )
        published_ae = Scope(
            organization_id=organization.id,
            client_id=clients[1].id,
            status="published",
            draft={},
            created_by_id=commercial.id,
        )
        foreign_draft = Scope(
            organization_id=organization.id,
            client_id=clients[2].id,
            status="draft",
            draft={},
            created_by_id=analyst_da.id,
        )
        own_draft = Scope(
            organization_id=organization.id,
            client_id=clients[3].id,
            status="draft",
            draft={},
            created_by_id=commercial.id,
        )
        outside_scope = Scope(
            organization_id=other_organization.id,
            client_id=clients[4].id,
            status="published",
            draft={},
            created_by_id=outsider.id,
        )
        db.session.add_all(
            [published_da, published_ae, foreign_draft, own_draft, outside_scope]
        )
        db.session.flush()

        db.session.add_all(
            [
                ScopeAssignment(
                    scope_id=published_da.id,
                    user_id=analyst_da.id,
                    role="ANALISTA_DA_IMPORT",
                    active=True,
                ),
                ScopeAssignment(
                    scope_id=published_ae.id,
                    user_id=analyst_ae.id,
                    role="ANALISTA_AE_IMPORT",
                    active=True,
                ),
                ScopeAssignment(
                    scope_id=foreign_draft.id,
                    user_id=analyst_da.id,
                    role="ANALISTA_DA_EXPORT",
                    active=True,
                ),
                ScopeAssignment(
                    scope_id=outside_scope.id,
                    user_id=outsider.id,
                    role="ANALISTA_DA_IMPORT",
                    active=True,
                ),
            ]
        )
        db.session.commit()

        yield app.test_client(), {
            "admin": _token(app, admin),
            "commercial": _token(app, commercial),
            "analyst_da_id": str(analyst_da.id),
            "da_tag_id": str(da_tag.id),
            "ae_tag_id": str(ae_tag.id),
            "outsider_tag_id": str(outsider_tag.id),
        }
        db.session.remove()
        db.drop_all()


def test_scopes_group_filters_users_by_tag_and_exposes_profile_tags(dashboard_api):
    client, context = dashboard_api

    response = client.get(
        "/dashboards/admin/scopes-by-user",
        headers=context["admin"],
        query_string={
            "status": "published",
            "groupBy": "analista_da",
            "tagId": context["da_tag_id"],
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["tagId"] == context["da_tag_id"]
    assert body["totalUsers"] == 1
    assert body["totalScopes"] == 1
    assert body["items"][0]["userId"] == context["analyst_da_id"]
    assert [tag["code"] for tag in body["items"][0]["userTags"]] == [
        "analista-da"
    ]


def test_tag_filter_is_applied_to_scope_client_and_metric_views(dashboard_api):
    client, context = dashboard_api
    query = {"status": "published", "tagId": context["da_tag_id"]}

    metrics = client.get(
        "/dashboards/admin/metrics",
        headers=context["admin"],
        query_string=query,
    ).get_json()
    clients = client.get(
        "/dashboards/admin/clients-by-user",
        headers=context["admin"],
        query_string={**query, "groupBy": "analista_da"},
    ).get_json()

    assert metrics["totalScopes"] == 1
    assert clients["totalUsers"] == 1
    assert clients["totalClients"] == 1


def test_user_detail_rejects_a_tag_not_assigned_to_selected_user(dashboard_api):
    client, context = dashboard_api

    response = client.get(
        f"/dashboards/admin/users/{context['analyst_da_id']}/scopes",
        headers=context["admin"],
        query_string={
            "status": "published",
            "groupBy": "analista_da",
            "tagId": context["ae_tag_id"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["items"] == []
    assert response.get_json()["total"] == 0


def test_tag_from_another_organization_never_matches(dashboard_api):
    client, context = dashboard_api

    response = client.get(
        "/dashboards/admin/metrics",
        headers=context["admin"],
        query_string={
            "status": "published",
            "tagId": context["outsider_tag_id"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["totalScopes"] == 0


def test_non_admin_dashboard_never_exposes_another_authors_draft(dashboard_api):
    client, context = dashboard_api

    admin_metrics = client.get(
        "/dashboards/admin/metrics",
        headers=context["admin"],
    ).get_json()
    commercial_metrics = client.get(
        "/dashboards/admin/metrics",
        headers=context["commercial"],
    ).get_json()

    assert admin_metrics["totalScopes"] == 4
    assert commercial_metrics["totalScopes"] == 3


def test_invalid_tag_filter_returns_json_validation_error(dashboard_api):
    client, context = dashboard_api

    response = client.get(
        "/dashboards/admin/metrics?tagId=not-a-uuid",
        headers=context["admin"],
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "dashboard_filter_error",
        "message": "tagId inválido.",
    }
