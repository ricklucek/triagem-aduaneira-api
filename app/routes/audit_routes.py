from datetime import datetime, time
from uuid import UUID

from flask import Blueprint, abort, g, jsonify, request
from sqlalchemy import Text, cast, or_

from ..auth import admin_required, auth_required
from ..extensions import db
from ..models import AuditEvent, AuditEventChange, Scope
from ..services.audit_service import (
    REVERSIBLE_ACTIONS,
    build_reversal_preview,
    reverse_audit_event,
)
from ..services.scope_processor import ScopeDataProcessor


audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


def _uuid_or_404(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        abort(404)


def _visible_events_query():
    query = (
        AuditEvent.query.join(
            AuditEventChange, AuditEventChange.event_id == AuditEvent.id
        )
        .filter(AuditEvent.organization_id == g.current_user.organization_id)
        .distinct()
    )
    if g.current_user.role == "admin":
        return query

    visible_scope_ids = ScopeDataProcessor(
        current_user=g.current_user
    ).scope_query_for_current_user().with_entities(Scope.id)
    return (
        query.filter(
            AuditEvent.module == "scopes",
            AuditEventChange.scope_id.in_(visible_scope_ids),
        )
        .distinct()
    )


def _load_visible_event(event_id):
    return _visible_events_query().filter(
        AuditEvent.id == _uuid_or_404(event_id)
    ).first_or_404()


def _iso(value):
    return value.isoformat() + "Z" if value else None


def _is_reversed(event_id) -> bool:
    return AuditEvent.query.filter_by(reverses_event_id=event_id).first() is not None


def _serialize_change(change: AuditEventChange, *, include_states: bool) -> dict:
    source = change.after_state or change.before_state or {}
    result = {
        "id": str(change.id),
        "entityType": change.entity_type,
        "entityId": str(change.entity_id),
        "scopeId": str(change.scope_id) if change.scope_id else None,
        "subjectUserId": str(change.subject_user_id) if change.subject_user_id else None,
        "clientId": str(change.client_id) if change.client_id else None,
        "label": source.get("clientShortName")
        or source.get("clientName")
        or source.get("name")
        or source.get("clientCnpj")
        or str(change.entity_id),
        "changedFields": change.changed_fields or [],
        "createdAt": _iso(change.created_at),
    }
    if include_states:
        result["before"] = change.before_state
        result["after"] = change.after_state
    return result


def _serialize_event(event: AuditEvent, *, include_changes: bool = False) -> dict:
    changes = AuditEventChange.query.filter_by(event_id=event.id).order_by(
        AuditEventChange.created_at.asc()
    ).all()
    result = {
        "id": str(event.id),
        "organizationId": str(event.organization_id),
        "actor": {
            "id": str(event.actor_user_id) if event.actor_user_id else None,
            "name": event.actor_name,
            "email": event.actor_email,
        },
        "module": event.module,
        "action": event.action,
        "entityType": event.entity_type,
        "entityId": str(event.entity_id) if event.entity_id else None,
        "operationId": str(event.operation_id) if event.operation_id else None,
        "title": event.title,
        "summary": event.summary,
        "metadata": event.details or {},
        "reversesEventId": str(event.reverses_event_id) if event.reverses_event_id else None,
        "reversible": event.action in REVERSIBLE_ACTIONS,
        "reversed": _is_reversed(event.id),
        "affectedCount": len(changes),
        "createdAt": _iso(event.created_at),
    }
    if include_changes:
        result["changes"] = [
            _serialize_change(change, include_states=True) for change in changes
        ]
    elif changes:
        result["targetLabel"] = _serialize_change(
            changes[0], include_states=False
        )["label"]
    return result


def _parse_date(value, *, end=False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        if len(str(value)) == 10:
            parsed = datetime.combine(parsed.date(), time.max if end else time.min)
        return parsed
    except ValueError:
        return None


@audit_bp.get("/events")
@auth_required
def list_audit_events():
    query = _visible_events_query()
    q = str(request.args.get("q") or "").strip()
    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                AuditEvent.title.ilike(term),
                AuditEvent.summary.ilike(term),
                AuditEvent.actor_name.ilike(term),
                AuditEvent.actor_email.ilike(term),
                AuditEvent.action.ilike(term),
                cast(AuditEventChange.before_state, Text).ilike(term),
                cast(AuditEventChange.after_state, Text).ilike(term),
            )
        ).distinct()
    if request.args.get("module"):
        query = query.filter(AuditEvent.module == request.args["module"])
    if request.args.get("action"):
        query = query.filter(AuditEvent.action == request.args["action"])
    if request.args.get("actorUserId"):
        query = query.filter(
            AuditEvent.actor_user_id == _uuid_or_404(request.args["actorUserId"])
        )

    date_from = _parse_date(request.args.get("dateFrom"))
    date_to = _parse_date(request.args.get("dateTo"), end=True)
    if date_from:
        query = query.filter(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.filter(AuditEvent.created_at <= date_to)

    try:
        limit = min(max(int(request.args.get("limit", 30)), 1), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify({"error": "bad_request", "message": "Paginação inválida."}), 400

    total = query.count()
    rows = query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset).all()
    return jsonify(
        {
            "items": [_serialize_event(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )


@audit_bp.get("/events/options")
@auth_required
def get_audit_event_options():
    query = _visible_events_query().subquery()
    modules = [
        row[0]
        for row in db.session.query(query.c.module).distinct().order_by(query.c.module).all()
    ]
    actions = [
        row[0]
        for row in db.session.query(query.c.action).distinct().order_by(query.c.action).all()
    ]
    actors = [
        {"id": str(row[0]) if row[0] else None, "name": row[1], "email": row[2]}
        for row in db.session.query(
            query.c.actor_user_id, query.c.actor_name, query.c.actor_email
        )
        .distinct()
        .order_by(query.c.actor_name)
        .all()
    ]
    return jsonify({"modules": modules, "actions": actions, "actors": actors})


@audit_bp.get("/events/<event_id>")
@auth_required
def get_audit_event(event_id: str):
    return jsonify(_serialize_event(_load_visible_event(event_id), include_changes=True))


@audit_bp.post("/events/<event_id>/reversal-preview")
@admin_required
def preview_audit_event_reversal(event_id: str):
    event = _load_visible_event(event_id)
    return jsonify(build_reversal_preview(event))


@audit_bp.post("/events/<event_id>/reverse")
@admin_required
def reverse_event(event_id: str):
    event = _load_visible_event(event_id)
    payload = request.get_json(silent=True) or {}
    if payload.get("confirmation") != "REVERTER":
        return jsonify(
            {
                "error": "confirmation_required",
                "message": 'Digite "REVERTER" para confirmar a operação.',
            }
        ), 400
    try:
        reversal, preview = reverse_audit_event(event, actor=g.current_user)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": "audit_reversal_error", "message": str(exc)}), 409
    except Exception:
        db.session.rollback()
        raise

    return jsonify(
        {
            "ok": True,
            "event": _serialize_event(reversal, include_changes=True),
            "result": {
                "reverted": preview["eligible"],
                "skipped": preview["skipped"],
                "conflicts": preview["conflicts"],
            },
        }
    )
