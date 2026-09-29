from datetime import datetime, timedelta

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import Organization, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "user-tags-test-secret"
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


@pytest.fixture
def api():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        organization = Organization(nome="Organização Tags", slug="org-tags")
        other_organization = Organization(nome="Outra Organização", slug="outra-org")
        db.session.add_all([organization, other_organization])
        db.session.flush()

        admin = User(
            organization_id=organization.id,
            nome="Admin Tags",
            email="admin-tags@example.invalid",
            role="admin",
            ativo=True,
        )
        admin.set_password("test-password")
        operator = User(
            organization_id=organization.id,
            nome="Operador Tags",
            email="operador-tags@example.invalid",
            role="operacao",
            ativo=True,
        )
        operator.set_password("test-password")
        outsider = User(
            organization_id=other_organization.id,
            nome="Admin Externo",
            email="admin-externo@example.invalid",
            role="admin",
            ativo=True,
        )
        outsider.set_password("test-password")
        db.session.add_all([admin, operator, outsider])
        db.session.commit()

        yield app.test_client(), {
            "admin": _token(app, admin),
            "operator": _token(app, operator),
            "outsider": _token(app, outsider),
            "admin_id": str(admin.id),
            "operator_id": str(operator.id),
        }
        db.session.remove()
        db.drop_all()


def test_default_tags_are_created_and_legacy_users_are_backfilled(api):
    client, context = api

    response = client.get(
        "/users/tags?include_inactive=true",
        headers=context["admin"],
    )

    assert response.status_code == 200
    tags = response.get_json()
    assert {tag["code"] for tag in tags} == {
        "admin",
        "comercial",
        "analista-da",
        "analista-ae",
        "credenciamento",
        "operacao",
    }
    admin_tag = next(tag for tag in tags if tag["code"] == "admin")
    assert admin_tag["is_master"] is True
    assert admin_tag["is_system"] is True

    users = client.get(
        "/users?include_inactive=true",
        headers=context["admin"],
    ).get_json()
    by_id = {user["id"]: user for user in users}
    assert [tag["code"] for tag in by_id[context["admin_id"]]["tags"]] == ["admin"]
    assert [tag["code"] for tag in by_id[context["operator_id"]]["tags"]] == [
        "operacao"
    ]


def test_user_accepts_multiple_operational_tags_and_admin_is_exclusive(api):
    client, context = api
    tags = client.get("/users/tags", headers=context["admin"]).get_json()
    by_code = {tag["code"]: tag for tag in tags}

    created = client.post(
        "/users",
        headers=context["admin"],
        json={
            "nome": "Analista Múltiplo",
            "email": "analista-multiplo@example.invalid",
            "password": "senha-segura",
            "role": "operacao",
            "setor": "Operações",
            "tag_ids": [
                by_code["analista-da"]["id"],
                by_code["analista-ae"]["id"],
            ],
        },
    )
    assert created.status_code == 201
    body = created.get_json()
    assert body["role"] == "operacao"
    assert {tag["code"] for tag in body["tags"]} == {"analista-da", "analista-ae"}

    promoted = client.put(
        f"/users/user/{body['id']}",
        headers=context["admin"],
        json={
            "role": "operacao",
            "tag_ids": [
                by_code["admin"]["id"],
                by_code["analista-da"]["id"],
            ],
        },
    )
    assert promoted.status_code == 200
    promoted_body = promoted.get_json()
    assert promoted_body["role"] == "admin"
    assert [tag["code"] for tag in promoted_body["tags"]] == ["admin"]


def test_custom_tag_can_be_created_filtered_and_inactivated(api):
    client, context = api
    created_tag = client.post(
        "/users/tags",
        headers=context["admin"],
        json={
            "name": "Financeiro",
            "description": "Conferência de cobranças.",
            "color": "amber",
        },
    )
    assert created_tag.status_code == 201
    tag = created_tag.get_json()
    assert tag["code"] == "financeiro"
    assert tag["is_system"] is False

    user = client.post(
        "/users",
        headers=context["admin"],
        json={
            "nome": "Usuário Financeiro",
            "email": "financeiro@example.invalid",
            "password": "senha-segura",
            "role": "operacao",
            "setor": "Financeiro",
            "tag_ids": [tag["id"]],
        },
    ).get_json()

    filtered = client.get(
        f"/users?include_inactive=true&tag_id={tag['id']}",
        headers=context["admin"],
    ).get_json()
    assert [row["id"] for row in filtered] == [user["id"]]

    disabled = client.patch(
        f"/users/tags/{tag['id']}",
        headers=context["admin"],
        json={"active": False},
    )
    assert disabled.status_code == 200
    assert disabled.get_json()["active"] is False

    active_tags = client.get("/users/tags", headers=context["admin"]).get_json()
    assert tag["id"] not in {row["id"] for row in active_tags}


def test_non_admin_cannot_manage_tags_or_users(api):
    client, context = api

    assert client.post(
        "/users/tags",
        headers=context["operator"],
        json={"name": "Indevida"},
    ).status_code == 403
    assert client.get("/users", headers=context["operator"]).status_code == 403
    assert client.get("/users/tags", headers=context["operator"]).status_code == 200


def test_user_changes_are_scoped_to_current_organization(api):
    client, context = api

    outsider_users = client.get(
        "/users?include_inactive=true",
        headers=context["outsider"],
    ).get_json()
    outsider_id = outsider_users[0]["id"]

    assert client.put(
        f"/users/user/{outsider_id}",
        headers=context["admin"],
        json={"nome": "Tentativa cruzada"},
    ).status_code == 404


def test_admin_cannot_deactivate_self_or_remove_last_admin(api):
    client, context = api
    tags = client.get("/users/tags", headers=context["admin"]).get_json()
    operation_tag = next(tag for tag in tags if tag["code"] == "operacao")

    assert client.delete(
        f"/users/user/{context['admin_id']}",
        headers=context["admin"],
    ).status_code == 400

    downgrade = client.put(
        f"/users/user/{context['admin_id']}",
        headers=context["admin"],
        json={
            "role": "operacao",
            "tag_ids": [operation_tag["id"]],
        },
    )
    assert downgrade.status_code == 400
    assert "ao menos um administrador" in downgrade.get_json()["message"]
