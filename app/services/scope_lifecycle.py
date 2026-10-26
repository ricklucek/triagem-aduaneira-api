from datetime import datetime

from app.scope_permissions import can_manage_scope_lifecycle

from .audit_service import record_scope_event, snapshot_scope


class ScopeLifecycleError(ValueError):
    def __init__(self, message, code="scope_inactive"):
        super().__init__(message)
        self.code = code


def ensure_scope_writable(scope):
    if scope.status == "archived":
        raise ScopeLifecycleError(
            "Escopo inativo. Reative-o antes de alterar os dados."
        )


def change_scope_activity(scope, *, actor, deactivate):
    if not can_manage_scope_lifecycle(actor):
        raise PermissionError(
            "Apenas administradores podem alterar a situação do escopo."
        )
    if scope.organization_id != actor.organization_id:
        raise PermissionError("Escopo de outra organização.")

    # Retried requests must not duplicate the audit event or overwrite the prior state.
    if deactivate == (scope.status == "archived"):
        return scope

    before = snapshot_scope(scope)
    now = datetime.utcnow()
    if deactivate:
        if scope.status not in ("draft", "published"):
            raise ScopeLifecycleError(
                "Estado do escopo inválido para inativação.", "invalid_scope_status"
            )
        scope.archived_from_status = scope.status
        scope.archived_at = now
        scope.archived_by_id = actor.id
        scope.status = "archived"
        action, label = "scope.deactivated", "inativado"
    else:
        # Legacy archived scopes have no prior state; never publish them implicitly.
        scope.status = (
            scope.archived_from_status
            if scope.archived_from_status in ("draft", "published")
            else "draft"
        )
        scope.archived_from_status = None
        scope.archived_at = None
        scope.archived_by_id = None
        action, label = "scope.reactivated", "reativado"
    scope.updated_at = now
    record_scope_event(
        actor=actor,
        scope=scope,
        action=action,
        title=f"Escopo {label}",
        summary=f"Escopo {label} pelo administrador, preservando dados e versões.",
        before_state=before,
        after_state=snapshot_scope(scope),
    )
    return scope
