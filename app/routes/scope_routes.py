from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from ..auth import auth_required
from ..extensions import db
from ..models import Admin, Scope, User
from ..schemas import ScopeSummarySchema
from ..scope_defaults import apply_admin_defaults, build_default_scope_draft, merge_scope_draft

scope_bp = Blueprint("scopes", __name__, url_prefix="/scopes")
summary_schema = ScopeSummarySchema(many=True)


def _serialize_admin_settings() -> dict:
    admin = Admin.query.order_by(Admin.created_at.asc()).first()
    if not admin:
        return {
            "salarioMinimoVigente": 0,
            "dadosBancariosCasco": {"banco": "", "agencia": "", "conta": ""},
        }
    return {
        "salarioMinimoVigente": float(admin.salario_minimo_vigente or 0),
        "dadosBancariosCasco": admin.dados_bancarios_casco or {"banco": "", "agencia": "", "conta": ""},
    }


def _serialize_responsibles() -> list[dict]:
    users = User.query.filter_by(ativo=True).order_by(User.nome.asc()).all()
    return [
        {
            "id": user.id,
            "nome": user.nome,
            "email": user.email,
            "role": user.role,
            "setor": user.setor,
        }
        for user in users
    ]


def _normalize_draft(draft: dict | None) -> dict:
    return apply_admin_defaults(merge_scope_draft(build_default_scope_draft(), draft or {}), _serialize_admin_settings())


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
            if value not in (None, "", []) and value != 0:
                filled_fields += 1

    walk(draft)
    return int((filled_fields / total_fields) * 100) if total_fields else 0


@scope_bp.get("/metadata")
@auth_required
def get_scope_metadata():
    return jsonify({"informacoesFixas": _serialize_admin_settings(), "responsaveis": _serialize_responsibles()})


@scope_bp.post("")
@auth_required
def create_scope():
    initial = request.get_json(silent=True) or {}
    draft = _normalize_draft(initial)

    scope = Scope(
        cnpj=(draft.get("sobreEmpresa") or {}).get("cnpj"),
        razao_social=(draft.get("sobreEmpresa") or {}).get("razaoSocial"),
        created_by_id=g.current_user.id,
        created_by_type=g.current_user_type,
        responsible_user_id=(draft.get("sobreEmpresa") or {}).get("responsavelComercialId"),
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
    return jsonify({"id": scope.id, "status": scope.status, "draft": _normalize_draft(scope.draft)})


@scope_bp.put("/<scope_id>")
@auth_required
def save_escope(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    normalized_draft = _normalize_draft(request.get_json(force=True))
    scope.draft = normalized_draft
    scope.cnpj = (normalized_draft.get("sobreEmpresa") or {}).get("cnpj")
    scope.razao_social = (normalized_draft.get("sobreEmpresa") or {}).get("razaoSocial")
    scope.responsible_user_id = (normalized_draft.get("sobreEmpresa") or {}).get("responsavelComercialId")
    scope.completeness_score = _calc_completeness(normalized_draft)
    db.session.commit()
    return "", 204


@scope_bp.post("/<scope_id>/publish")
@auth_required
def publish_scope(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    now = datetime.utcnow()

    scope.status = "published"
    scope.last_published_at = now

    return jsonify({"scope_id": scope.id, "published_at": now.isoformat() + "Z"})

@scope_bp.delete("/<scope_id>")
@auth_required
def delete_scope(scope_id: str):
    scope = Scope.query.get_or_404(scope_id)
    db.session.delete(scope)
    db.session.commit()
    return "", 204