from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from app.schemas.scopes.response import ScopeStructuredSchema

from ..auth import auth_required
from ..extensions import db
from ..models import Client, Scope, ScopeAssignment, ScopeVersion, User
from ..schemas import UserSchema
from ..services.scope_processor import ScopeDataProcessor, ScopePublishValidationError

scope_bp = Blueprint("scopes", __name__, url_prefix="/scopes")


def _processor() -> ScopeDataProcessor:
    return ScopeDataProcessor(current_user=g.current_user)


def _load_scope_payload() -> dict:
    payload = request.get_json(force=True)
    return payload if isinstance(payload, dict) else {}


def _load_optional_json_payload() -> dict:
    payload = request.get_json(silent=True) or {}
    return payload if isinstance(payload, dict) else {}


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


def _admin_forbidden_response():
    if getattr(g.current_user, "role", None) != "admin":
        return jsonify({"error": "forbidden", "message": "Endpoint permitido apenas para admin."}), 403
    return None


def _serialize_responsibles() -> list[dict]:
    query = User.query.filter_by(active=True)
    if g.current_user.organization_id:
        query = query.filter_by(organization_id=g.current_user.organization_id)

    users = query.order_by(User.name.asc()).all()
    return [
        {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "department": user.department,
        }
        for user in users
    ]


@scope_bp.get("/metadata")
@auth_required
def get_scope_metadata():
    processor = _processor()
    return jsonify(
        {
            "fixedInfo": processor.get_admin_settings(),
            "informacoesFixas": processor.get_admin_settings(),  # compatibilidade temporária
            "responsaveis": _serialize_responsibles(),
        }
    )


@scope_bp.post("")
@auth_required
def create_scope():
    processor = _processor()
    draft = processor.normalize_draft(_load_optional_json_payload())

    scope = Scope(
        organization_id=g.current_user.organization_id,
        created_by_id=g.current_user.id,
        draft=draft,
        status="draft",
        version=1,
    )

    db.session.add(scope)
    db.session.commit()
    return jsonify({"id": str(scope.id)}), 201


@scope_bp.get("/<scope_id>/draft")
@auth_required
def get_scope_draft(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()

    return jsonify(
        {
            "id": str(scope.id),
            "status": scope.status,
            "version": scope.version,
            "draft": processor.build_form_scope_from_draft(scope.draft),
        }
    )


@scope_bp.put("/<scope_id>/draft")
@auth_required
def save_scope_draft(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()

    processor.save_draft(scope, _load_scope_payload())
    db.session.commit()

    return jsonify(
        {
            "scope_id": str(scope.id),
            "draft_saved": True,
            "updated_at": scope.updated_at.isoformat() + "Z" if scope.updated_at else None,
        }
    )

@scope_bp.put("/<scope_id>")
@auth_required
def update_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()

    processor.save_draft(scope, _load_scope_payload())
    db.session.commit()

    return jsonify({"scope_id": str(scope.id), "draft_saved": True})


@scope_bp.post("/<scope_id>/publish")
@auth_required
def publish_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()

    payload = _load_optional_json_payload()
    incoming_draft = payload.get("draft")
    if isinstance(incoming_draft, dict):
        processor.save_draft(scope, incoming_draft)

    try:
        result = processor.publish_scope(scope)
    except ScopePublishValidationError as exc:
        db.session.rollback()
        return jsonify({"error": "validation_error", "message": str(exc), "errors": exc.errors}), 400
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": "bad_request", "message": str(exc)}), 400

    db.session.commit()
    return jsonify(result)


@scope_bp.get("")
@auth_required
def list_scopes():
    processor = _processor()
    params = request.args.to_dict()
    query = processor.scope_query_for_current_user()

    if params.get("status"):
        query = query.filter(Scope.status == params["status"])
    if params.get("client_id"):
        query = query.filter(Scope.client_id == params["client_id"])
    if params.get("responsible_user_id"):
        query = query.filter(Scope.commercial_responsible_user_id == params["responsible_user_id"])
    if params.get("created_by_id"):
        query = query.filter(Scope.created_by_id == params["created_by_id"])
    if params.get("assigned_user_id"):
        query = query.join(ScopeAssignment, ScopeAssignment.scope_id == Scope.id).filter(
            ScopeAssignment.user_id == params["assigned_user_id"],
            ScopeAssignment.active.is_(True),
        )
    if params.get("cnpj"):
        query = query.join(Client, Scope.client_id == Client.id).filter(Client.tax_id == params["cnpj"])
    if params.get("q"):
        term = f"%{params['q']}%"
        query = query.outerjoin(Client, Scope.client_id == Client.id).filter(
            or_(Client.legal_name.ilike(term), Client.tax_id.ilike(term), Scope.status.ilike(term))
        )

    total = query.count()
    limit = _int_arg("limit", 20)
    offset = _int_arg("offset", 0)
    scopes = query.order_by(Scope.updated_at.desc().nullslast(), Scope.created_at.desc()).limit(limit).offset(offset).all()

    return jsonify(
        {
            "items": [processor.build_scope_summary(scope) for scope in scopes],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@scope_bp.get("/<scope_id>")
@auth_required
def get_scope(scope_id: str):
    processor = _processor()
    row = (
        processor.scope_query_for_current_user()
        .join(User, Scope.created_by_id == User.id)
        .with_entities(Scope, User)
        .filter(Scope.id == scope_id)
        .first_or_404()
    )
    scope, user = row

    return jsonify(
        {
            **ScopeStructuredSchema().dump(scope),
            "created_by": UserSchema(only=["id", "name", "email", "role", "department"]).dump(user),
        }
    )


@scope_bp.get("/bulk/assignment-summary")
@auth_required
def get_bulk_assignment_summary():
    forbidden = _admin_forbidden_response()
    if forbidden:
        return forbidden

    processor = _processor()
    group_by = request.args.get("groupBy")

    try:
        return jsonify(processor.get_bulk_assignment_summary(group_by))
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400


@scope_bp.get("/bulk/assignment-scopes")
@auth_required
def get_bulk_assignment_scopes():
    forbidden = _admin_forbidden_response()
    if forbidden:
        return forbidden

    processor = _processor()
    group_by = request.args.get("groupBy")
    user_id = request.args.get("userId")

    if not user_id:
        return jsonify({"error": "bad_request", "message": "userId é obrigatório."}), 400

    try:
        return jsonify(processor.get_bulk_assignment_scopes(group_by, user_id))
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400


@scope_bp.post("/bulk/assignment-update")
@auth_required
def bulk_update_assignment():
    forbidden = _admin_forbidden_response()
    if forbidden:
        return forbidden

    processor = _processor()
    payload = _load_optional_json_payload()

    try:
        result = processor.bulk_update_assignment(
            group_by=payload.get("groupBy"),
            from_user_id=payload.get("fromUserId"),
            to_user_id=payload.get("toUserId"),
            scope_ids=payload.get("scopeIds") or [],
        )
    except ValueError as exc:
        return jsonify({"error": "bad_request", "message": str(exc)}), 400

    db.session.commit()
    return jsonify(result)


@scope_bp.get("/user/assigned-count")
@auth_required
def count_user_assigned_scopes():
    processor = _processor()
    query = processor.scope_query_for_current_user()

    query_responsible_user_id = query.filter(Scope.commercial_responsible_user_id == g.current_user.id)
    query_created_by_id = query.filter(Scope.created_by_id == g.current_user.id)
    query_assigned_user_id = query.join(ScopeAssignment, ScopeAssignment.scope_id == Scope.id).filter(
        ScopeAssignment.user_id == g.current_user.id,
        ScopeAssignment.active.is_(True),
    )

    return jsonify(
        [
            {"type": "responsible_user_id", "count": query_responsible_user_id.count()},
            {"type": "created_by_id", "count": query_created_by_id.count()},
            {"type": "assigned_user_id", "count": query_assigned_user_id.count()},
        ]
    )


@scope_bp.get("/<scope_id>/versions")
@auth_required
def list_scope_versions(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    rows = ScopeVersion.query.filter_by(scope_id=scope.id).order_by(ScopeVersion.version_number.desc()).all()
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


@scope_bp.delete("/<scope_id>")
@auth_required
def delete_scope(scope_id: str):
    processor = _processor()
    scope = processor.scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    db.session.delete(scope)
    db.session.commit()
    return "", 204
