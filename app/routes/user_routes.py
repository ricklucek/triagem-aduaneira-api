from uuid import UUID

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..auth import admin_required, auth_required
from ..extensions import db
from ..models import User, UserTag, UserTagAssignment
from ..schemas import UserSchema
from ..services.user_tags import (
    ALLOWED_TAG_COLORS,
    UserTagError,
    assert_admin_can_be_removed,
    ensure_default_user_tags,
    ensure_legacy_user_tag,
    is_admin_user,
    normalize_access_role,
    replace_user_tags,
    serialize_user_tag,
    slugify_tag,
)

user_bp = Blueprint("users", __name__, url_prefix="/users")
user_schema = UserSchema()


def _parse_bool(value, *, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _uuid_or_404(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        abort(404)


def _user_query():
    query = User.query.options(
        selectinload(User.tag_assignments).selectinload(UserTagAssignment.tag)
    )
    if g.current_user.organization_id:
        query = query.filter(User.organization_id == g.current_user.organization_id)
    return query


def _load_user(user_id: str) -> User:
    return _user_query().filter(User.id == _uuid_or_404(user_id)).first_or_404()


def _bootstrap_user_tags() -> None:
    organization_id = g.current_user.organization_id
    if not organization_id:
        return
    ensure_default_user_tags(organization_id, created_by_id=g.current_user.id)
    for user in _user_query().all():
        ensure_legacy_user_tag(user, actor_id=g.current_user.id)
    db.session.commit()


def _error_response(exc: Exception, status=400):
    db.session.rollback()
    return jsonify({"error": "user_profile_error", "message": str(exc)}), status


@user_bp.get("")
@admin_required
def list_users():
    _bootstrap_user_tags()
    query = _user_query().order_by(User.ativo.desc(), User.nome.asc())

    if not _parse_bool(request.args.get("include_inactive"), default=False):
        query = query.filter(User.ativo.is_(True))
    if request.args.get("active") is not None:
        query = query.filter(
            User.ativo.is_(_parse_bool(request.args.get("active")))
        )
    if request.args.get("tag_id"):
        query = query.join(
            UserTagAssignment,
            UserTagAssignment.user_id == User.id,
        ).filter(
            UserTagAssignment.tag_id == _uuid_or_404(request.args["tag_id"])
        )
    if request.args.get("q"):
        term = f"%{request.args['q'].strip()}%"
        query = query.filter(
            or_(
                User.nome.ilike(term),
                User.email.ilike(term),
                User.setor.ilike(term),
            )
        )

    return jsonify(UserSchema(many=True).dump(query.distinct().all()))


@user_bp.get("/responsibles")
@auth_required
def list_responsibles():
    query = _user_query().filter(User.ativo.is_(True)).order_by(User.nome.asc())
    return jsonify(UserSchema(many=True).dump(query.all()))


@user_bp.get("/tags")
@auth_required
def list_tags():
    organization_id = g.current_user.organization_id
    if not organization_id:
        return jsonify([])

    ensure_default_user_tags(organization_id, created_by_id=g.current_user.id)
    db.session.commit()

    query = UserTag.query.filter(UserTag.organization_id == organization_id)
    include_inactive = (
        g.current_user.role == "admin"
        and _parse_bool(request.args.get("include_inactive"), default=False)
    )
    if not include_inactive:
        query = query.filter(UserTag.active.is_(True))

    rows = query.order_by(UserTag.is_master.desc(), UserTag.name.asc()).all()
    result = []
    for tag in rows:
        item = serialize_user_tag(tag)
        item["users_count"] = UserTagAssignment.query.filter_by(tag_id=tag.id).count()
        result.append(item)
    return jsonify(result)


@user_bp.post("/tags")
@admin_required
def create_tag():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    if not name or len(name) > 80:
        return _error_response(UserTagError("Informe um nome de tag com até 80 caracteres."))

    code = slugify_tag(name)
    if not code:
        return _error_response(UserTagError("Não foi possível gerar o código da tag."))
    color = str(payload.get("color") or "slate").strip().lower()
    if color not in ALLOWED_TAG_COLORS:
        return _error_response(UserTagError("Cor de tag inválida."))

    if UserTag.query.filter_by(
        organization_id=g.current_user.organization_id,
        code=code,
    ).first():
        return _error_response(UserTagError("Já existe uma tag com este nome."), 409)

    tag = UserTag(
        organization_id=g.current_user.organization_id,
        code=code,
        name=name,
        description=(str(payload.get("description") or "").strip() or None),
        color=color,
        is_master=False,
        is_system=False,
        active=True,
        created_by_id=g.current_user.id,
    )
    db.session.add(tag)
    db.session.commit()
    return jsonify(serialize_user_tag(tag)), 201


@user_bp.patch("/tags/<tag_id>")
@admin_required
def update_tag(tag_id: str):
    tag = UserTag.query.filter_by(
        id=_uuid_or_404(tag_id),
        organization_id=g.current_user.organization_id,
    ).first_or_404()
    payload = request.get_json(silent=True) or {}

    if "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name or len(name) > 80:
            return _error_response(UserTagError("Informe um nome de tag com até 80 caracteres."))
        tag.name = name
    if "description" in payload:
        tag.description = str(payload.get("description") or "").strip() or None
    if "color" in payload:
        color = str(payload.get("color") or "").strip().lower()
        if color not in ALLOWED_TAG_COLORS:
            return _error_response(UserTagError("Cor de tag inválida."))
        tag.color = color
    if "active" in payload:
        active = bool(payload["active"])
        if tag.is_master and not active:
            return _error_response(UserTagError("A tag Admin não pode ser inativada."))
        tag.active = active

    db.session.commit()
    item = serialize_user_tag(tag)
    item["users_count"] = UserTagAssignment.query.filter_by(tag_id=tag.id).count()
    return jsonify(item)


@user_bp.post("")
@admin_required
def create_user():
    payload = request.get_json(silent=True) or {}
    try:
        role = normalize_access_role(payload.get("role") or "operacao")
    except UserTagError as exc:
        return _error_response(exc)

    nome = str(payload.get("nome") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not nome or not email:
        return _error_response(UserTagError("Nome e e-mail são obrigatórios."))
    if len(password) < 8:
        return _error_response(UserTagError("A senha deve possuir ao menos 8 caracteres."))
    if User.query.filter_by(email=email).first():
        return _error_response(UserTagError("E-mail já está em uso."), 409)

    user = User(
        nome=nome,
        email=email,
        role=role,
        setor=str(payload.get("setor") or "").strip() or None,
        ativo=bool(payload.get("ativo", True)),
        organization_id=g.current_user.organization_id,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    ensure_default_user_tags(user.organization_id, created_by_id=g.current_user.id)
    tag_ids = payload.get("tag_ids")
    if tag_ids is None:
        default = UserTag.query.filter_by(
            organization_id=user.organization_id,
            code=role,
            active=True,
        ).first()
        tag_ids = [str(default.id)] if default else []

    try:
        replace_user_tags(
            user,
            tag_ids,
            actor=g.current_user,
            requested_role=role,
        )
        db.session.commit()
    except (UserTagError, IntegrityError) as exc:
        return _error_response(exc, 409 if isinstance(exc, IntegrityError) else 400)

    return jsonify(user_schema.dump(_load_user(str(user.id)))), 201


@user_bp.put("/user/<user_id>")
@admin_required
def update_user(user_id: str):
    user = _load_user(user_id)
    payload = request.get_json(silent=True) or {}
    was_admin = is_admin_user(user)

    if "nome" in payload:
        nome = str(payload.get("nome") or "").strip()
        if not nome:
            return _error_response(UserTagError("Nome é obrigatório."))
        user.nome = nome
    if "email" in payload:
        email = str(payload.get("email") or "").strip().lower()
        if not email:
            return _error_response(UserTagError("E-mail é obrigatório."))
        conflict = User.query.filter(User.email == email, User.id != user.id).first()
        if conflict:
            return _error_response(UserTagError("E-mail já está em uso."), 409)
        user.email = email
    if "setor" in payload:
        user.setor = str(payload.get("setor") or "").strip() or None
    if payload.get("password"):
        if len(str(payload["password"])) < 8:
            return _error_response(UserTagError("A senha deve possuir ao menos 8 caracteres."))
        user.set_password(str(payload["password"]))
    if "ativo" in payload:
        if user.id == g.current_user.id and not bool(payload["ativo"]):
            return _error_response(UserTagError("Você não pode inativar o próprio usuário."))
        user.ativo = bool(payload["ativo"])

    requested_role = payload.get("role")
    try:
        if "tag_ids" in payload:
            replace_user_tags(
                user,
                payload.get("tag_ids") or [],
                actor=g.current_user,
                requested_role=requested_role,
            )
        elif requested_role is not None:
            role = normalize_access_role(requested_role)
            replace_user_tags(
                user,
                [str(item.tag_id) for item in user.tag_assignments],
                actor=g.current_user,
                requested_role=role,
            )

        if was_admin and (not user.ativo or user.role != "admin"):
            assert_admin_can_be_removed(user)
        db.session.commit()
    except (UserTagError, IntegrityError) as exc:
        return _error_response(exc, 409 if isinstance(exc, IntegrityError) else 400)

    return jsonify(user_schema.dump(_load_user(str(user.id))))


@user_bp.delete("/user/<user_id>")
@admin_required
def delete_user(user_id: str):
    user = _load_user(user_id)
    if user.id == g.current_user.id:
        return _error_response(UserTagError("Você não pode inativar o próprio usuário."))
    if is_admin_user(user):
        try:
            assert_admin_can_be_removed(user)
        except UserTagError as exc:
            return _error_response(exc)
    user.ativo = False
    db.session.commit()
    return jsonify({"ok": True, "message": "Usuário inativado com sucesso."})
