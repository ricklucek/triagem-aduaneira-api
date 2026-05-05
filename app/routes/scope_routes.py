from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import and_, or_

from ..auth import auth_required
from ..extensions import db
from ..models import Client, Scope, ScopeAssignment, ScopeVersion, User
from ..schemas import ScopeBulkResponsibleSchema, ScopeListQuerySchema, ScopeSchema, UserSchema
from ..services.scope_processor import ScopeDataProcessor

scope_bp = Blueprint("scopes", __name__, url_prefix="/scopes")
scope_schema = ScopeSchema()
scope_list_query_schema = ScopeListQuerySchema()
bulk_responsible_schema = ScopeBulkResponsibleSchema()


def _processor() -> ScopeDataProcessor:
    return ScopeDataProcessor(current_user=g.current_user)


def _load_scope_payload() -> dict:
    payload = request.get_json(force=True)
    return payload if isinstance(payload, dict) else {}


def _serialize_responsibles() -> list[dict]:
    query = User.query.filter_by(ativo=True)
    if g.current_user.organization_id:
        query = query.filter_by(organization_id=g.current_user.organization_id)

    users = query.order_by(User.nome.asc()).all()
    return [
        {
            "id": str(user.id),
            "nome": user.nome,
            "email": user.email,
            "role": user.role,
            "setor": user.setor,
        }
        for user in users
    ]


@scope_bp.get("/metadata")
@auth_required
def get_scope_metadata():
    processor = _processor()
    return jsonify({"informacoesFixas": processor.get_admin_settings(), "responsaveis": _serialize_responsibles()})


@scope_bp.post("")
@auth_required
def create_scope():
    processor = _processor()
    draft = processor.normalize_draft(_load_scope_payload())

    scope = Scope(
        organization_id=g.current_user.organization_id,
        created_by_id=g.current_user.id,
        draft=draft,
        version=1,
    )
    processor.apply_draft_to_scope(scope, draft)

    db.session.add(scope)
    db.session.flush()

    processor.upsert_client_from_draft(scope, draft)
    processor.sync_assignments_from_draft(scope, draft)
    processor.sync_services_from_draft(scope, draft)
    processor.sync_prepostos_from_draft(scope, draft)

    db.session.commit()
    return jsonify({"id": str(scope.id)}), 201


@scope_bp.get("")
@auth_required
def list_scopes():
    processor = _processor()
    params = scope_list_query_schema.load(request.args)

    query = processor.scope_query_for_current_user()

    if params.get("status"):
        query = query.filter(Scope.status == params["status"])
    if params.get("client_id"):
        query = query.filter(Scope.client_id == params["client_id"])
    if params.get("responsible_user_id"):
        query = query.filter(Scope.responsible_user_id == params["responsible_user_id"])
    if params.get("created_by_id"):
        query = query.filter(Scope.created_by_id == params["created_by_id"])
    if params.get("cnpj"):
        query = query.join(Client, Scope.client_id == Client.id).filter(Client.cnpj == params["cnpj"])
    if params.get("q"):
        term = f"%{params['q']}%"
        query = query.outerjoin(Client, Scope.client_id == Client.id).filter(
            or_(Client.razao_social.ilike(term), Client.cnpj.ilike(term), Scope.status.ilike(term))
        )

    total = query.count()
    scopes = (
        query.order_by(Scope.updated_at.desc().nullslast(), Scope.created_at.desc())
        .limit(params["limit"])
        .offset(params["offset"])
        .all()
    )

    return jsonify(
        {
            "items": [processor.build_scope_summary(scope) for scope in scopes],
            "total": total,
            "limit": params["limit"],
            "offset": params["offset"],
        }
    )


@scope_bp.get("/<scope_id>")
@auth_required
def get_scope(scope_id: str):
    processor = _processor()
    scope_query = (
        processor.scope_query_for_current_user()
        .join(User, Scope.created_by_id == User.id)
        .with_entities(Scope, User)
        .filter(Scope.id == scope_id)
        .first_or_404()
    )
    scope, user = scope_query

    return jsonify(
        {
            **scope_schema.dump(scope),
            "created_by": UserSchema(only=["id", "nome", "email", "role", "setor"]).dump(user),
        }
    )


@scope_bp.put("/<scope_id>")
@auth_required
def update_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    normalized_draft = processor.normalize_draft(_load_scope_payload())

    processor.apply_draft_to_scope(scope, normalized_draft)
    processor.upsert_client_from_draft(scope, normalized_draft)
    processor.sync_assignments_from_draft(scope, normalized_draft)
    processor.sync_services_from_draft(scope, normalized_draft)
    processor.sync_prepostos_from_draft(scope, normalized_draft)

    db.session.commit()
    return jsonify(scope_schema.dump(scope))


@scope_bp.post("/<scope_id>/publish")
@auth_required
def publish_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    now = datetime.utcnow()

    normalized_draft = processor.normalize_draft(scope.draft)
    processor.apply_draft_to_scope(scope, normalized_draft)
    processor.upsert_client_from_draft(scope, normalized_draft)
    processor.sync_assignments_from_draft(scope, normalized_draft)
    processor.sync_services_from_draft(scope, normalized_draft)
    processor.sync_prepostos_from_draft(scope, normalized_draft)

    scope.status = "published"
    scope.last_published_at = now
    scope.published_snapshot = normalized_draft
    scope.version = (scope.version or 0) + 1

    db.session.flush()
    db.session.add(
        ScopeVersion(
            scope_id=scope.id,
            version_number=scope.version,
            draft_snapshot=normalized_draft,
            published_snapshot=normalized_draft,
            created_by_id=g.current_user.id,
        )
    )

    db.session.commit()
    return jsonify({"scope_id": str(scope.id), "published_at": now.isoformat() + "Z", "client_id": str(scope.client_id)})


@scope_bp.post("/<scope_id>/sync")
@auth_required
def sync_scope(scope_id: str):
    """Sincroniza um escopo específico com a arquitetura relacional.

    Body opcional:
        {"dryRun": true}

    Se dryRun=true, apenas retorna o que está faltando.
    Se dryRun=false, cria/atualiza Client, ScopeAssignment, ScopeService e ScopePreposto.
    """
    processor = _processor()
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dryRun", True))

    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    result = processor.sync_scope(scope, dry_run=dry_run)

    if not dry_run and result.changed:
        db.session.commit()

    return jsonify(result.to_dict())


@scope_bp.post("/sync-missing")
@auth_required
def sync_missing_scopes():
    """Sincroniza escopos antigos da organização atual em lote.

    Body opcional:
        {
            "dryRun": true,
            "limit": 100,
            "status": "published"
        }
    """
    processor = _processor()
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dryRun", True))
    limit = min(int(payload.get("limit", 100)), 500)

    query = processor.scope_query_for_current_user().order_by(Scope.created_at.asc())
    if payload.get("status"):
        query = query.filter(Scope.status == payload["status"])

    scopes = query.limit(limit).all()
    results = processor.sync_scopes(scopes, dry_run=dry_run)

    if not dry_run:
        db.session.commit()

    return jsonify(
        {
            "dryRun": dry_run,
            "checked": len(results),
            "alreadySynced": sum(1 for item in results if item.already_synced),
            "changed": sum(1 for item in results if item.changed),
            "items": [item.to_dict() for item in results],
        }
    )


@scope_bp.get("/<scope_id>/versions")
@auth_required
def list_scope_versions(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    rows = (
        ScopeVersion.query.filter_by(scope_id=scope.id)
        .order_by(ScopeVersion.version_number.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": str(row.id),
                "version_number": row.version_number,
                "created_at": row.created_at.isoformat() + "Z",
                "created_by_id": str(row.created_by_id),
            }
            for row in rows
        ]
    )


@scope_bp.post("/bulk/reassign-responsible")
@auth_required
def bulk_reassign_responsible():
    payload = bulk_responsible_schema.load(request.get_json(force=True))

    filters = [Scope.responsible_user_id == payload["old_user_id"]]
    if g.current_user.organization_id:
        filters.append(Scope.organization_id == g.current_user.organization_id)
    if payload["apply_status"]:
        filters.append(Scope.status.in_(payload["apply_status"]))

    scopes = Scope.query.filter(and_(*filters)).all()
    impacted_scope_ids = [str(scope.id) for scope in scopes]

    if payload["dry_run"]:
        return jsonify({"dryRun": True, "impactedScopes": impacted_scope_ids, "count": len(impacted_scope_ids)})

    now = datetime.utcnow()
    for scope in scopes:
        scope.responsible_user_id = payload["new_user_id"]

        assignment_query = ScopeAssignment.query.filter_by(
            scope_id=scope.id,
            role="RESPONSAVEL_COMERCIAL",
        )
        if payload["only_active_assignments"]:
            assignment_query = assignment_query.filter_by(active=True)

        active_role = assignment_query.all()

        for assignment in active_role:
            assignment.active = False
            assignment.ends_at = now

        db.session.add(
            ScopeAssignment(
                scope_id=scope.id,
                user_id=payload["new_user_id"],
                role="RESPONSAVEL_COMERCIAL",
                active=True,
                starts_at=now,
            )
        )

    db.session.commit()

    return jsonify(
        {
            "dryRun": False,
            "updatedCount": len(impacted_scope_ids),
            "updatedScopeIds": impacted_scope_ids,
        }
    )


@scope_bp.delete("/<scope_id>")
@auth_required
def delete_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    db.session.delete(scope)
    db.session.commit()
    return "", 204
