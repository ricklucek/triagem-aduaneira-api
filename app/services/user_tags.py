from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlalchemy import or_

from ..extensions import db
from ..models import User, UserTag, UserTagAssignment


DEFAULT_USER_TAGS = (
    {
        "code": "admin",
        "name": "Admin",
        "description": "Acesso administrativo mestre da organização.",
        "color": "rose",
        "is_master": True,
    },
    {
        "code": "comercial",
        "name": "Comercial",
        "description": "Atuação comercial e responsabilidade por clientes.",
        "color": "emerald",
    },
    {
        "code": "analista-da",
        "name": "Analista DA",
        "description": "Analista de despacho aduaneiro.",
        "color": "blue",
    },
    {
        "code": "analista-ae",
        "name": "Analista AE",
        "description": "Analista de assessoria especial.",
        "color": "violet",
    },
    {
        "code": "credenciamento",
        "name": "Credenciamento",
        "description": "Atuação em cadastros e credenciamentos.",
        "color": "amber",
    },
    {
        "code": "operacao",
        "name": "Operação",
        "description": "Atuação operacional geral.",
        "color": "slate",
    },
)

ALLOWED_ACCESS_ROLES = {"admin", "comercial", "credenciamento", "operacao"}
ALLOWED_TAG_COLORS = {"slate", "blue", "emerald", "amber", "violet", "rose"}


class UserTagError(ValueError):
    pass


def normalize_access_role(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "administrador":
        normalized = "admin"
    if normalized not in ALLOWED_ACCESS_ROLES:
        allowed = ", ".join(sorted(ALLOWED_ACCESS_ROLES))
        raise UserTagError(f"Nível de acesso inválido. Valores aceitos: {allowed}.")
    return normalized


def slugify_tag(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def ensure_default_user_tags(organization_id, *, created_by_id=None) -> list[UserTag]:
    existing = {
        row.code: row
        for row in UserTag.query.filter_by(organization_id=organization_id).all()
    }
    created = False
    for definition in DEFAULT_USER_TAGS:
        if definition["code"] in existing:
            continue
        row = UserTag(
            organization_id=organization_id,
            created_by_id=created_by_id,
            is_system=True,
            active=True,
            **definition,
        )
        db.session.add(row)
        existing[row.code] = row
        created = True
    if created:
        db.session.flush()
    return list(existing.values())


def _uuid_set(values) -> set[UUID]:
    result: set[UUID] = set()
    for value in values or []:
        try:
            result.add(UUID(str(value)))
        except (TypeError, ValueError):
            raise UserTagError("Uma ou mais tags possuem identificador inválido.") from None
    return result


def tags_for_user(user: User) -> list[UserTag]:
    return sorted(
        (assignment.tag for assignment in user.tag_assignments if assignment.tag),
        key=lambda tag: (not tag.is_master, tag.name.lower()),
    )


def serialize_user_tag(tag: UserTag) -> dict:
    return {
        "id": str(tag.id),
        "organization_id": str(tag.organization_id),
        "code": tag.code,
        "name": tag.name,
        "description": tag.description,
        "color": tag.color,
        "is_master": bool(tag.is_master),
        "is_system": bool(tag.is_system),
        "active": bool(tag.active),
        "created_at": tag.created_at.isoformat() + "Z" if tag.created_at else None,
        "updated_at": tag.updated_at.isoformat() + "Z" if tag.updated_at else None,
    }


def replace_user_tags(
    user: User,
    tag_ids,
    *,
    actor: User,
    requested_role: str | None,
) -> str:
    selected_ids = _uuid_set(tag_ids)
    selected = (
        UserTag.query.filter(
            UserTag.organization_id == user.organization_id,
            UserTag.id.in_(selected_ids),
            UserTag.active.is_(True),
        ).all()
        if selected_ids
        else []
    )
    if len(selected) != len(selected_ids):
        raise UserTagError("Uma ou mais tags não existem, estão inativas ou pertencem a outra organização.")

    master_tags = [tag for tag in selected if tag.is_master]
    if master_tags:
        selected = [master_tags[0]]
        next_role = "admin"
    else:
        if requested_role is None and user.role == "admin":
            raise UserTagError(
                "Informe um nível de acesso não administrativo ao remover a tag Admin."
            )
        next_role = normalize_access_role(requested_role or user.role)
        if next_role == "admin":
            defaults = ensure_default_user_tags(
                user.organization_id,
                created_by_id=actor.id,
            )
            master = next(tag for tag in defaults if tag.is_master)
            selected = [master]

    current_by_tag = {
        assignment.tag_id: assignment for assignment in user.tag_assignments
    }
    desired_ids = {tag.id for tag in selected}
    for tag_id, assignment in list(current_by_tag.items()):
        if tag_id not in desired_ids:
            db.session.delete(assignment)

    for tag in selected:
        if tag.id in current_by_tag:
            continue
        db.session.add(
            UserTagAssignment(
                user=user,
                tag=tag,
                assigned_by_id=actor.id,
            )
        )

    user.role = next_role
    return next_role


def ensure_legacy_user_tag(user: User, *, actor_id=None) -> None:
    if user.tag_assignments:
        return
    tags = ensure_default_user_tags(user.organization_id, created_by_id=actor_id)
    by_code = {tag.code: tag for tag in tags}
    role = "admin" if user.role == "administrador" else user.role
    tag = by_code.get(role)
    if not tag:
        return
    db.session.add(
        UserTagAssignment(
            user=user,
            tag=tag,
            assigned_by_id=actor_id,
        )
    )
    if role == "admin" and user.role != "admin":
        user.role = "admin"


def is_admin_user(user: User) -> bool:
    if user.role in {"admin", "administrador"}:
        return True
    return any(tag.is_master for tag in tags_for_user(user))


def assert_admin_can_be_removed(user: User) -> None:
    remaining = User.query.filter(
        User.organization_id == user.organization_id,
        User.id != user.id,
        User.ativo.is_(True),
        or_(User.role == "admin", User.role == "administrador"),
    ).count()
    if remaining == 0:
        raise UserTagError("A organização precisa manter ao menos um administrador ativo.")
