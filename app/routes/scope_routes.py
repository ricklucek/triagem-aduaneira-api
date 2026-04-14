from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import and_, or_

from ..auth import auth_required
from ..extensions import db
from ..models import Client, OrganizationSetting, Scope, ScopeAssignment, ScopeVersion, User
from ..schemas import ScopeBulkResponsibleSchema, ScopeListQuerySchema, ScopeSchema
from ..scope_defaults import apply_admin_defaults, build_default_scope_draft, merge_scope_draft

scope_bp = Blueprint("scopes", __name__, url_prefix="/scopes")
scope_schema = ScopeSchema()
scope_list_query_schema = ScopeListQuerySchema()
bulk_responsible_schema = ScopeBulkResponsibleSchema()


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


def _get_admin_settings() -> dict:
    default = {
        "salarioMinimoVigente": 0,
        "dadosBancariosCasco": {"banco": "", "agencia": "", "conta": ""},
    }
    if not g.current_user.organization_id:
        return default

    row = OrganizationSetting.query.filter_by(
        organization_id=g.current_user.organization_id,
        key="scope_fixed_info",
    ).first()
    if not row:
        return default
    return row.value_json or default


def _normalize_draft(draft: dict | None) -> dict:
    return apply_admin_defaults(merge_scope_draft(build_default_scope_draft(), draft or {}), _get_admin_settings())


def _load_scope_payload() -> dict:
    payload = request.get_json(force=True)
    if not isinstance(payload, dict):
        return {}
    return payload


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


def _scope_query_for_current_user():
    q = Scope.query
    if g.current_user.organization_id:
        q = q.filter(Scope.organization_id == g.current_user.organization_id)
    return q


def _build_scope_summary(scope: Scope) -> dict:
    return {
        "id": str(scope.id),
        "status": scope.status,
        "completeness_score": scope.completeness_score,
        "version": scope.version,
        "updated_at": scope.updated_at,
        "last_published_at": scope.last_published_at,
        "client_id": str(scope.client_id) if scope.client_id else None,
        "client_cnpj": scope.client.cnpj if scope.client else None,
        "client_razao_social": scope.client.razao_social if scope.client else None,
        "responsible_user_id": str(scope.responsible_user_id) if scope.responsible_user_id else None,
        "responsible_user_nome": scope.responsible_user.nome if scope.responsible_user else None,
    }


def _upsert_client_from_draft(scope: Scope, normalized_draft: dict):
    sobre_empresa = normalized_draft.get("sobreEmpresa") or {}
    cnpj = (sobre_empresa.get("cnpj") or "").strip()
    razao_social = (sobre_empresa.get("razaoSocial") or "").strip()

    if not cnpj or not razao_social or not scope.organization_id:
        return None

    client = Client.query.filter_by(organization_id=scope.organization_id, cnpj=cnpj).first()
    if not client:
        client = Client(
            organization_id=scope.organization_id,
            cnpj=cnpj,
            razao_social=razao_social,
        )
        db.session.add(client)

    client.nome_resumido = sobre_empresa.get("nomeResumido")
    client.inscricao_estadual = sobre_empresa.get("inscricaoEstadual")
    client.inscricao_municipal = sobre_empresa.get("inscricaoMunicipal")
    client.endereco_completo_escritorio = sobre_empresa.get("enderecoCompletoEscritorio")
    client.endereco_completo_armazem = sobre_empresa.get("enderecoCompletoArmazem")
    client.cnae_principal = sobre_empresa.get("cnaePrincipal")
    client.cnae_secundario = sobre_empresa.get("cnaeSecundario")
    client.regime_tributacao = sobre_empresa.get("regimeTributacao")

    scope.client = client
    return client


@scope_bp.get("/metadata")
@auth_required
def get_scope_metadata():
    return jsonify({"informacoesFixas": _get_admin_settings(), "responsaveis": _serialize_responsibles()})


@scope_bp.post("")
@auth_required
def create_scope():
    initial = _load_scope_payload()
    draft = _normalize_draft(initial)
    sobre_empresa = draft.get("sobreEmpresa") or {}

    scope = Scope(
        organization_id=g.current_user.organization_id,
        created_by_id=g.current_user.id,
        responsible_user_id=sobre_empresa.get("responsavelComercial") or sobre_empresa.get("responsavelComercialId"),
        draft=draft,
        completeness_score=_calc_completeness(draft),
        version=1,
    )
    db.session.add(scope)
    db.session.flush()

    if scope.responsible_user_id:
        db.session.add(
            ScopeAssignment(
                scope_id=scope.id,
                user_id=scope.responsible_user_id,
                role="RESPONSAVEL_COMERCIAL",
                active=True,
            )
        )

    db.session.commit()
    return jsonify({"id": str(scope.id)}), 201


@scope_bp.get("")
@auth_required
def list_scopes():
    params = scope_list_query_schema.load(request.args)

    query = _scope_query_for_current_user()

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
            "items": [_build_scope_summary(scope) for scope in scopes],
            "total": total,
            "limit": params["limit"],
            "offset": params["offset"],
        }
    )


@scope_bp.get("/<scope_id>")
@auth_required
def get_scope(scope_id: str):
    scope = _scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    return jsonify(scope_schema.dump(scope))


@scope_bp.put("/<scope_id>")
@auth_required
def update_scope(scope_id: str):
    scope = _scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    normalized_draft = _normalize_draft(_load_scope_payload())

    scope.draft = normalized_draft
    scope.completeness_score = _calc_completeness(normalized_draft)
    sobre_empresa = normalized_draft.get("sobreEmpresa") or {}
    scope.responsible_user_id = sobre_empresa.get("responsavelComercial") or sobre_empresa.get("responsavelComercialId")

    db.session.commit()
    return jsonify(scope_schema.dump(scope))


@scope_bp.post("/<scope_id>/publish")
@auth_required
def publish_scope(scope_id: str):
    scope = _scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    now = datetime.utcnow()

    normalized_draft = _normalize_draft(scope.draft)
    scope.draft = normalized_draft
    _upsert_client_from_draft(scope, normalized_draft)

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


@scope_bp.get("/<scope_id>/versions")
@auth_required
def list_scope_versions(scope_id: str):
    scope = _scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
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
    scope = _scope_query_for_current_user().filter(Scope.id == scope_id).first_or_404()
    db.session.delete(scope)
    db.session.commit()
    return "", 204
