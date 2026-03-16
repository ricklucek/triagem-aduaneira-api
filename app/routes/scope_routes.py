from datetime import datetime

from app.scope_defaults import build_default_scope_draft, merge_scope_draft
from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from ..auth import auth_required
from ..extensions import db
from ..models import Scope, ScopeVersion
from ..schemas import ScopeSummarySchema

scope_bp = Blueprint("scopes", __name__, url_prefix="/scopes")
summary_schema = ScopeSummarySchema(many=True)


def _calc_completeness(draft: dict) -> int:
    if not isinstance(draft, dict) or not draft:
        return 0
    total_fields = 0
    filled_fields = 0

    def walk(value):
        nonlocal total_fields, filled_fields
        if isinstance(value, dict):
            for sub in value.values():
                walk(sub)
        elif isinstance(value, list):
            total_fields += 1
            if len(value) > 0:
                filled_fields += 1
        else:
            total_fields += 1
            if value not in (None, "", []):
                filled_fields += 1

    walk(draft)
    return int((filled_fields / total_fields) * 100) if total_fields else 0


@scope_bp.post("")
@auth_required
def create_scope():
    initial = request.get_json(silent=True) or {}
    
    draft = merge_scope_draft(build_default_scope_draft(), initial)

    scope = Scope(
        id=f"scope_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        cnpj=(draft.get("sobreEmpresa") or {}).get("cnpj"),
        razao_social=(draft.get("sobreEmpresa") or {}).get("razaoSocial"),
        created_by=g.current_user.id,
        draft=draft,
        completeness_score=_calc_completeness(draft),
    )
    db.session.add(scope)
    db.session.commit()
    return jsonify({"id": scope.id}), 201


@scope_bp.get("")
@auth_required
def list_scopes():
    status = request.args.get("status")
    cnpj = request.args.get("cnpj")
    q = request.args.get("q")
    limit = int(request.args.get("limit", 10))
    offset = int(request.args.get("offset", 0))

    query = Scope.query
    if status:
        query = query.filter(Scope.status == status)
    if cnpj:
        query = query.filter(Scope.cnpj == cnpj)
    if q:
        term = f"%{q}%"
        query = query.filter(or_(Scope.razao_social.ilike(term), Scope.cnpj.ilike(term)))

    total = query.count()
    scopes = query.order_by(Scope.updated_at.desc()).limit(limit).offset(offset).all()

    return jsonify({"items": summary_schema.dump(scopes), "total": total, "limit": limit, "offset": offset})


@scope_bp.get("/<scope_id>")
@auth_required
def get_scope(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    draft = merge_scope_draft(build_default_scope_draft(), scope.draft or {})
    return jsonify({"id": scope.id, "status": scope.status, "draft": draft})


@scope_bp.put("/<scope_id>/draft")
@auth_required
def save_draft(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    draft = request.get_json(force=True)
    
    normalized_draft = merge_scope_draft(build_default_scope_draft(), draft)
    scope.draft = normalized_draft
    scope.cnpj = (normalized_draft.get("sobreEmpresa") or {}).get("cnpj")
    scope.razao_social = (normalized_draft.get("sobreEmpresa") or {}).get("razaoSocial")
    scope.completeness_score = _calc_completeness(normalized_draft)
    
    db.session.commit()
    return "", 204


@scope_bp.post("/<scope_id>/publish")
@auth_required
def publish_scope(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    next_version = scope.version_count + 1
    now = datetime.utcnow()

    scope.status = "published"
    scope.version_count = next_version
    scope.last_published_at = now

    version = ScopeVersion(scope_id=scope.id, version_number=next_version, published_at=now, data=scope.draft)
    db.session.add(version)
    db.session.commit()

    return jsonify({"scope_id": scope.id, "version_number": next_version, "published_at": now.isoformat() + "Z"})


@scope_bp.get("/<scope_id>/versions")
@auth_required
def list_versions(scope_id: str):
    versions = ScopeVersion.query.filter_by(scope_id=scope_id).order_by(ScopeVersion.version_number.desc()).all()
    return jsonify(
        [
            {
                "version_number": v.version_number,
                "published_at": v.published_at.isoformat() + "Z",
                "data": v.data,
            }
            for v in versions
        ]
    )