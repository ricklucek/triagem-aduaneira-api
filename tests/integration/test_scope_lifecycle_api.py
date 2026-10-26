from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app import create_app
from app.extensions import db
from app.models import AuditEvent, Client, Organization, Scope, ScopeVersion, User
from app.services.audit_service import record_scope_event, snapshot_scope
from app.services.scope_processor import ScopeDataProcessor


class Config:
    TESTING = True
    SECRET_KEY = "scope-lifecycle-test"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def api():
    app = create_app(Config)
    with app.app_context():
        db.create_all()
        org = Organization(nome="Lifecycle", slug="lifecycle")
        other = Organization(nome="Other", slug="other-lifecycle")
        db.session.add_all([org, other])
        db.session.flush()
        users = {}
        for name, role, organization in [
            ("admin", "admin", org),
            ("owner", "operacao", org),
            ("commercial", "comercial", org),
            ("outsider", "admin", other),
        ]:
            user = User(
                nome=name,
                email=f"{name}@example.invalid",
                role=role,
                organization_id=organization.id,
                ativo=True,
            )
            user.set_password("test-password")
            db.session.add(user)
            users[name] = user
        db.session.flush()
        client = Client(
            organization_id=org.id,
            razao_social="Lifecycle client",
            cnpj="00144009000176",
            ativo=True,
        )
        db.session.add(client)
        db.session.flush()
        payload = {
            "sobreEmpresa": {"cnpj": client.cnpj, "razaoSocial": client.razao_social},
            "contatos": [{"nome": "Diego"}],
            "operacao": {"tipos": []},
        }
        scopes = {}
        for status in ("draft", "published"):
            scope = Scope(
                organization_id=org.id,
                client_id=client.id if status == "published" else None,
                created_by_id=users["owner"].id,
                responsible_user_id=users["owner"].id,
                status=status,
                version=3,
                draft=deepcopy(payload),
                published_snapshot=deepcopy(payload) if status == "published" else None,
            )
            if status == "draft":
                scope.draft["sobreEmpresa"]["cnpj"] = ""
            db.session.add(scope)
            scopes[status] = scope
        db.session.flush()
        db.session.add(
            ScopeVersion(
                scope_id=scopes["published"].id,
                version_number=3,
                draft_snapshot=payload,
                published_snapshot=payload,
                created_by_id=users["owner"].id,
            )
        )
        db.session.commit()
        now = datetime.utcnow()
        headers = {
            name: {
                "Authorization": "Bearer "
                + jwt.encode(
                    {
                        "sub": str(user.id),
                        "type": "access",
                        "exp": now + timedelta(hours=1),
                    },
                    Config.SECRET_KEY,
                    algorithm="HS256",
                )
            }
            for name, user in users.items()
        }
        yield app.test_client(), scopes, users, headers, client
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize("original_status", ["draft", "published"])
def test_deactivate_and_reactivate_preserve_data_versions_and_audit(
    api, original_status
):
    http, scopes, users, headers, client = api
    scope = scopes[original_status]
    original = deepcopy(scope.draft)
    published = deepcopy(scope.published_snapshot)
    path = f"/scopes/{scope.id}"
    response = http.post(path + "/deactivate", headers=headers["admin"])
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "archived"
    assert data["archived_from_status"] == original_status
    assert data["archived_by_id"] == str(users["admin"].id)
    assert data["archived_at"]
    assert scope.draft == original and scope.published_snapshot == published
    assert scope.version == 3 and client.ativo
    assert http.post(path + "/deactivate", headers=headers["admin"]).status_code == 200
    assert AuditEvent.query.filter_by(action="scope.deactivated").count() == 1
    assert http.get(path + "/versions", headers=headers["admin"]).status_code == 200
    assert (
        http.post(path + "/reactivate", headers=headers["admin"]).get_json()["status"]
        == original_status
    )
    assert (
        scope.archived_from_status is None
        and scope.archived_at is None
        and scope.archived_by_id is None
    )
    assert (
        scope.draft == original
        and scope.published_snapshot == published
        and scope.version == 3
    )
    assert ScopeVersion.query.count() == 1
    assert http.post(path + "/reactivate", headers=headers["admin"]).status_code == 200
    event = AuditEvent.query.filter_by(action="scope.reactivated").one()
    assert event.actor_user_id == users["admin"].id


@pytest.mark.parametrize("role", ["owner", "commercial", "outsider"])
@pytest.mark.parametrize("action", ["deactivate", "reactivate"])
def test_lifecycle_authorization_and_organization_isolation(api, role, action):
    http, scopes, _, headers, _ = api
    response = http.post(
        f"/scopes/{scopes['published'].id}/{action}", headers=headers[role]
    )
    assert response.status_code == (404 if role == "outsider" else 403)
    assert scopes["published"].status == "published"


def test_filters_pagination_and_private_inactive_access(api):
    http, scopes, _, headers, client = api
    scope_id = str(scopes["published"].id)
    http.post(f"/scopes/{scope_id}/deactivate", headers=headers["admin"])
    for query in ("", "?include_drafts=true", "?activity=active"):
        result = http.get("/scopes" + query, headers=headers["admin"]).get_json()
        assert scope_id not in {row["id"] for row in result["items"]}
    for query in (
        "?activity=inactive",
        "?activity=inactive&include_drafts=true",
        "?status=archived",
    ):
        result = http.get("/scopes" + query, headers=headers["admin"]).get_json()
        assert result["total"] == 1 and result["items"][0]["id"] == scope_id
    assert (
        http.get("/scopes?activity=all", headers=headers["admin"]).get_json()["total"]
        == 2
    )
    assert (
        http.get(
            "/scopes?activity=inactive&limit=1&offset=1", headers=headers["admin"]
        ).get_json()["items"]
        == []
    )
    assert (
        http.get("/scopes?activity=all", headers=headers["outsider"]).get_json()[
            "total"
        ]
        == 0
    )
    for role in ("owner", "commercial"):
        for query in ("?activity=inactive", "?activity=all", "?status=archived"):
            assert http.get("/scopes" + query, headers=headers[role]).status_code == 403
        for suffix in ("", "/versions"):
            assert (
                http.get(
                    f"/scopes/{scope_id}{suffix}", headers=headers[role]
                ).status_code
                == 404
            )
        assert (
            http.get(f"/clients/{client.id}/scopes", headers=headers[role]).get_json()[
                "total"
            ]
            == 0
        )
        assert (
            http.get(f"/clients?cnpj={client.cnpj}", headers=headers[role]).get_json()[
                "items"
            ][0]["scope_id"]
            is None
        )
        items = http.get(
            "/scopes?include_drafts=true", headers=headers[role]
        ).get_json()["items"]
        assert all(row["id"] != scope_id for row in items)


def test_inactive_scope_blocks_all_direct_writes_and_keeps_client_association(api):
    http, scopes, _, headers, client = api
    scope = scopes["published"]
    path = f"/scopes/{scope.id}"
    http.post(path + "/deactivate", headers=headers["admin"])
    for method, suffix, payload in [
        ("put", "", {"status": "published"}),
        ("post", "/publish", {}),
        ("post", "/sync", {"dryRun": False}),
        ("delete", "", {}),
    ]:
        response = getattr(http, method)(
            path + suffix, json=payload, headers=headers["admin"]
        )
        assert response.status_code == 409
        assert response.get_json()["error"] == "scope_inactive"
    assert (
        http.post(
            "/scopes/sync-missing", json={"dryRun": False}, headers=headers["admin"]
        ).get_json()["checked"]
        == 1
    )
    assert scope.status == "archived" and scope.client_id == client.id
    assert (
        http.post(
            f"/scopes?clientId={client.id}", json={}, headers=headers["admin"]
        ).status_code
        == 409
    )


def test_audit_reversal_cannot_reactivate_inactive_scope(api):
    http, scopes, users, headers, _ = api
    scope = scopes["published"]
    before = snapshot_scope(scope)
    scope.draft = {**scope.draft, "geral": {"descricao": "updated"}}
    event = record_scope_event(
        actor=users["admin"],
        scope=scope,
        action="scope.updated",
        title="Update",
        summary="Test update",
        before_state=before,
        after_state=snapshot_scope(scope),
    )
    db.session.commit()
    event_id = event.id
    http.post(f"/scopes/{scope.id}/deactivate", headers=headers["admin"])
    preview = http.post(
        f"/audit/events/{event_id}/reversal-preview", headers=headers["admin"]
    ).get_json()
    assert preview["eligible"] == 0 and preview["conflicts"] == 1
    assert (
        http.post(
            f"/audit/events/{event_id}/reverse",
            json={"confirmation": "REVERTER"},
            headers=headers["admin"],
        ).status_code
        == 409
    )
    assert scope.status == "archived"


def test_legacy_bulk_operations_skip_inactive_scope(api):
    http, scopes, users, headers, _ = api
    scope = scopes["published"]
    http.post(f"/scopes/{scope.id}/deactivate", headers=headers["admin"])
    processor = ScopeDataProcessor(users["admin"])
    result = processor.bulk_update_assignment(
        "responsavel_comercial",
        str(users["owner"].id),
        str(users["commercial"].id),
        [str(scope.id)],
    )
    assert result["impactedScopes"] == 0
    assert scope.responsible_user_id == users["owner"].id


def test_legacy_archived_scope_reactivates_as_draft(api):
    http, scopes, _, headers, _ = api
    scope = scopes["published"]
    scope.status = "archived"
    db.session.commit()
    assert (
        http.post(
            f"/scopes/{scope.id}/reactivate", headers=headers["admin"]
        ).get_json()["status"]
        == "draft"
    )


def test_dashboard_metrics_and_assignment_counts_exclude_inactive_scopes(api):
    http, scopes, _, headers, _ = api
    before = http.get("/dashboards/admin/metrics", headers=headers["admin"]).get_json()
    assert before["totalScopes"] == 2
    http.post(f"/scopes/{scopes['published'].id}/deactivate", headers=headers["admin"])
    after = http.get("/dashboards/admin/metrics", headers=headers["admin"]).get_json()
    assert after["totalScopes"] == 1
    counts = http.get(
        "/scopes/user/assigned-count", headers=headers["owner"]
    ).get_json()
    assert (
        next(item["count"] for item in counts if item["type"] == "created_by_id") == 1
    )


def test_mixed_audit_event_hides_inactive_scope_snapshots_from_regular_users(api):
    http, scopes, users, headers, _ = api
    operation_id = uuid4()
    for scope in scopes.values():
        event = record_scope_event(
            actor=users["admin"],
            scope=scope,
            action="scope.bulk_updated",
            title="Bulk update",
            summary="Two scopes",
            before_state=snapshot_scope(scope),
            after_state=snapshot_scope(scope),
            operation_id=operation_id,
            append_operation=True,
        )
    db.session.commit()
    event_id = event.id
    http.post(f"/scopes/{scopes['published'].id}/deactivate", headers=headers["admin"])
    detail = http.get(f"/audit/events/{event_id}", headers=headers["owner"]).get_json()
    assert detail["affectedCount"] == 1
    assert detail["changes"][0]["scopeId"] == str(scopes["draft"].id)
    admin_detail = http.get(
        f"/audit/events/{event_id}", headers=headers["admin"]
    ).get_json()
    assert admin_detail["affectedCount"] == 2


def test_invalid_filter_is_rejected(api):
    http, _, _, headers, _ = api
    assert (
        http.get("/scopes?activity=invalid", headers=headers["admin"]).status_code
        == 400
    )
