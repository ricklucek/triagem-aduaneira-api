from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_

from ..extensions import db
from ..models import (
    AuditEvent,
    AuditEventChange,
    Scope,
    ScopeVersion,
    User,
)


SENSITIVE_KEY_PARTS = (
    "password",
    "senha",
    "secret",
    "token",
    "private_key",
    "certificate_data",
    "pfx",
    "p12",
)

REVERSIBLE_ACTIONS = {"scope.updated", "scope.bulk_updated"}


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized_key = str(key)
            if any(part in normalized_key.lower() for part in SENSITIVE_KEY_PARTS):
                continue
            result[normalized_key] = _json_value(item)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def sanitize_audit_value(value: Any) -> Any:
    """Return a JSON-safe copy without credentials or certificate material."""

    return _json_value(deepcopy(value))


def snapshot_scope(scope: Scope) -> dict[str, Any]:
    return sanitize_audit_value(
        {
            "id": scope.id,
            "status": scope.status,
            "draft": scope.draft or {},
            "publishedSnapshot": scope.published_snapshot,
            "version": scope.version,
            "lastPublishedAt": scope.last_published_at,
            "responsibleUserId": scope.responsible_user_id,
            "clientId": scope.client_id,
            "clientName": scope.client.razao_social if scope.client else None,
            "clientShortName": scope.client.nome_resumido if scope.client else None,
            "clientCnpj": scope.client.cnpj if scope.client else None,
        }
    )


def snapshot_user(user: User, *, password_changed: bool = False) -> dict[str, Any]:
    tags = []
    for assignment in user.tag_assignments:
        if not assignment.tag:
            continue
        tags.append(
            {
                "id": str(assignment.tag.id),
                "code": assignment.tag.code,
                "name": assignment.tag.name,
            }
        )
    tags.sort(key=lambda item: (item["name"].lower(), item["id"]))
    result = {
        "id": str(user.id),
        "name": user.nome,
        "email": user.email,
        "role": user.role,
        "department": user.setor,
        "active": user.ativo,
        "tags": tags,
    }
    if password_changed:
        result["credentialsChanged"] = True
    return result


def snapshot_tag(tag) -> dict[str, Any]:
    return sanitize_audit_value(
        {
            "id": tag.id,
            "code": tag.code,
            "name": tag.name,
            "description": tag.description,
            "color": tag.color,
            "isMaster": tag.is_master,
            "isSystem": tag.is_system,
            "active": tag.active,
        }
    )


def changed_fields(before: Any, after: Any, prefix: str = "") -> list[str]:
    before = sanitize_audit_value(before)
    after = sanitize_audit_value(after)
    if isinstance(before, dict) and isinstance(after, dict):
        fields: list[str] = []
        for key in sorted(set(before) | set(after)):
            path = f"{prefix}.{key}" if prefix else key
            fields.extend(changed_fields(before.get(key), after.get(key), path))
        return fields
    if before != after:
        return [prefix or "value"]
    return []


def record_audit_event(
    *,
    actor: User,
    module: str,
    action: str,
    entity_type: str,
    entity_id=None,
    title: str,
    summary: str | None = None,
    details: dict | None = None,
    operation_id=None,
    reverses_event_id=None,
    append_operation: bool = False,
) -> AuditEvent:
    event = None
    if append_operation and operation_id:
        event = AuditEvent.query.filter_by(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            operation_id=operation_id,
            action=action,
        ).first()
    if event:
        return event

    event = AuditEvent(
        organization_id=actor.organization_id,
        actor_user_id=actor.id,
        actor_name=actor.nome,
        actor_email=actor.email,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        operation_id=operation_id,
        title=title,
        summary=summary,
        details=sanitize_audit_value(details or {}),
        reverses_event_id=reverses_event_id,
    )
    db.session.add(event)
    db.session.flush()
    return event


def add_audit_change(
    event: AuditEvent,
    *,
    entity_type: str,
    entity_id,
    before_state: dict | None,
    after_state: dict | None,
    scope_id=None,
    subject_user_id=None,
    client_id=None,
) -> AuditEventChange:
    before = sanitize_audit_value(before_state)
    after = sanitize_audit_value(after_state)
    change = AuditEventChange(
        event_id=event.id,
        organization_id=event.organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        scope_id=scope_id,
        subject_user_id=subject_user_id,
        client_id=client_id,
        before_state=before,
        after_state=after,
        changed_fields=changed_fields(before, after),
    )
    db.session.add(change)
    return change


def record_scope_event(
    *,
    actor: User,
    scope: Scope,
    action: str,
    title: str,
    summary: str | None,
    before_state: dict | None,
    after_state: dict | None,
    details: dict | None = None,
    operation_id=None,
    append_operation: bool = False,
) -> AuditEvent:
    event = record_audit_event(
        actor=actor,
        module="scopes",
        action=action,
        entity_type="scope",
        entity_id=scope.id,
        title=title,
        summary=summary,
        details=details,
        operation_id=operation_id,
        append_operation=append_operation,
    )
    add_audit_change(
        event,
        entity_type="scope",
        entity_id=scope.id,
        scope_id=scope.id,
        client_id=scope.client_id,
        before_state=before_state,
        after_state=after_state,
    )
    return event


def _scope_conflict_state(snapshot: dict | None) -> dict | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.get("status"),
        "draft": snapshot.get("draft") or {},
        "publishedSnapshot": snapshot.get("publishedSnapshot"),
        "responsibleUserId": snapshot.get("responsibleUserId"),
        "clientId": snapshot.get("clientId"),
    }


def _already_reversed_entity_ids(source_event_id) -> set[str]:
    rows = (
        db.session.query(AuditEventChange.entity_id)
        .join(AuditEvent, AuditEvent.id == AuditEventChange.event_id)
        .filter(AuditEvent.reverses_event_id == source_event_id)
        .all()
    )
    return {str(row[0]) for row in rows}


def build_reversal_preview(event: AuditEvent) -> dict[str, Any]:
    changes = AuditEventChange.query.filter_by(event_id=event.id).all()
    reversed_ids = _already_reversed_entity_ids(event.id)
    items = []

    for change in changes:
        status = "eligible"
        reason = None
        scope = None
        if event.action not in REVERSIBLE_ACTIONS or change.entity_type != "scope":
            status = "unsupported"
            reason = "Este tipo de alteração é somente para consulta."
        elif str(change.entity_id) in reversed_ids:
            status = "already_reversed"
            reason = "Esta alteração já foi revertida."
        else:
            scope = db.session.get(Scope, change.entity_id)
            if not scope or scope.organization_id != event.organization_id:
                status = "missing"
                reason = "O escopo não existe mais."
            elif _scope_conflict_state(snapshot_scope(scope)) != _scope_conflict_state(
                change.after_state
            ):
                status = "conflict"
                reason = "O escopo foi alterado depois desta operação."

        source = change.after_state or change.before_state or {}
        items.append(
            {
                "changeId": str(change.id),
                "entityId": str(change.entity_id),
                "label": source.get("clientShortName")
                or source.get("clientName")
                or source.get("clientCnpj")
                or str(change.entity_id),
                "status": status,
                "reason": reason,
                "changedFields": change.changed_fields or [],
            }
        )

    return {
        "eventId": str(event.id),
        "reversible": event.action in REVERSIBLE_ACTIONS,
        "eligible": sum(1 for item in items if item["status"] == "eligible"),
        "conflicts": sum(1 for item in items if item["status"] == "conflict"),
        "skipped": sum(1 for item in items if item["status"] != "eligible"),
        "items": items,
    }


def reverse_audit_event(event: AuditEvent, *, actor: User) -> tuple[AuditEvent, dict[str, Any]]:
    from .scope_processor import ScopeDataProcessor

    preview = build_reversal_preview(event)
    eligible_ids = {
        item["changeId"] for item in preview["items"] if item["status"] == "eligible"
    }
    if not eligible_ids:
        raise ValueError("Não há alterações elegíveis para reversão.")

    reversal = record_audit_event(
        actor=actor,
        module="scopes",
        action="scope.reversed",
        entity_type="scope",
        entity_id=event.entity_id,
        title=f"Reversão: {event.title}",
        summary=f"Reversão compensatória da operação de {event.created_at.isoformat()}.",
        details={"sourceEventId": str(event.id)},
        reverses_event_id=event.id,
    )
    processor = ScopeDataProcessor(current_user=actor)

    for change in AuditEventChange.query.filter_by(event_id=event.id).all():
        if str(change.id) not in eligible_ids:
            continue
        scope = db.session.get(Scope, change.entity_id)
        current = snapshot_scope(scope)
        target = deepcopy(change.before_state or {})
        current_version = scope.version or 0

        scope.status = target.get("status") or scope.status
        scope.draft = deepcopy(target.get("draft") or {})
        scope.published_snapshot = deepcopy(target.get("publishedSnapshot"))
        scope.responsible_user_id = (
            UUID(str(target["responsibleUserId"]))
            if target.get("responsibleUserId")
            else None
        )
        scope.client_id = (
            UUID(str(target["clientId"])) if target.get("clientId") else None
        )

        processor.upsert_client_from_draft(scope, scope.draft)
        processor.sync_assignments_from_draft(scope, scope.draft)
        processor.sync_services_from_draft(scope, scope.draft)
        processor.sync_prepostos_from_draft(scope, scope.draft)

        if scope.status == "published":
            now = datetime.utcnow()
            scope.version = current_version + 1
            scope.last_published_at = now
            db.session.flush()
            db.session.add(
                ScopeVersion(
                    scope_id=scope.id,
                    version_number=scope.version,
                    draft_snapshot=deepcopy(scope.draft),
                    published_snapshot=deepcopy(scope.published_snapshot),
                    created_by_id=actor.id,
                )
            )

        db.session.flush()
        restored = snapshot_scope(scope)
        add_audit_change(
            reversal,
            entity_type="scope",
            entity_id=scope.id,
            scope_id=scope.id,
            client_id=scope.client_id,
            before_state=current,
            after_state=restored,
        )

    return reversal, preview
